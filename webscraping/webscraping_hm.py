## Imports
import logging
import os 
import re 
import logging
import sqlite3 
import requests
import numpy as np
import pandas as pd

from bs4        import BeautifulSoup
from datetime   import datetime
from sqlalchemy import create_engine

## Data Collection 
def data_collection( url, headers ):

    # Request to URL 
    page = requests.get( url, headers=headers )

    # Beautiful Soup object
    soup = BeautifulSoup( page.text, 'html.parser' )

    # ==============================Product Data========================================

    products = soup.find( 'ul', class_='products-listing small' )

    product_list = products.find_all( 'article', class_='hm-product-item')

    # product id
    product_id = [p.get( 'data-articlecode' ) for p in product_list]

    # product category
    product_category = [p.get( 'data-category' ) for p in product_list]

    # product name
    product_list = products.find_all( 'a', class_='link' )
    product_name = [p.get_text() for p in product_list]

    # price
    product_list = products.find_all( 'span', class_='price regular' )
    product_price = [p.get_text() for p in product_list]

    data = pd.DataFrame( [product_id, product_category, product_name, product_price] ).T
    data.columns = ['product_id', 'product_category', 'product_name', 'product_price']

    return data

## Data Collection by Product 
def data_collection_by_product( data, headers ):
    # empty dataframe
    df_compositions = pd.DataFrame() 

    # unique columns for all products
    aux = []

    df_pattern = pd.DataFrame( columns=['Art. No.', 'Composition', 'Fit', 'Product safety', 'Size'] )
    for i in range ( len( data ) ):
        # API Requests
        url = 'https://www2.hm.com/en_us/productpage.' + data.loc[i, 'product_id' ] + '.html'
        logger.debug ( 'Product: %s', url )
            
        page = requests.get( url, headers=headers )

        # Beautiful Soup object
        soup = BeautifulSoup( page.text, 'html.parser' )
            
        # ================================= Color Name =================================
        product_list = soup.find_all( 'a', class_='filter-option miniature active' ) + soup.find_all('a', class_='filter-option miniature')
        color_name = [p.get( 'data-color') for p in product_list]

        # product id 
        product_id = [p.get( 'data-articlecode' ) for p in product_list]

        df_color = pd.DataFrame( [product_id, color_name] ).T
        df_color.columns = ['product_id', 'color_name']
        
        for j in range( len( df_color ) ):
            # API Requests
            url = 'https://www2.hm.com/en_us/productpage.' + df_color.loc[j, 'product_id' ] + '.html'
            logger.debug ( 'Color: %s', url )
            
            page = requests.get( url, headers=headers )

            # Beautiful Soup object
            soup = BeautifulSoup( page.text, 'html.parser' )
                
            #================================= Product Name =================================
            product_name = soup.find_all('section', class_='product-name-price')
            product_name = product_name[0].get_text()
            #print( product_name )                                        
                                                                    
                
            # ================================= Product Price =================================
            product_price = soup.find_all( 'div', class_='primary-row product-item-price' )
            #product_price = re.findall( r'\d+\.?d+', product_price[0].get_text() )[0]
            product_price = product_price[0].get_text()
            #print( product_price )                                                         
                                                                
            # ================================= Composition =================================
            # HTML all data stored 
            product_composition_list = soup.find_all( 'div', class_='details-attributes-list-item' )
            product_composition = [list(filter(None, p.get_text().split( '\n' ) ) ) for p in product_composition_list]

            # Collect the size here                             
            size_text = soup.find_all('dd')[0].text
            size_text = size_text if 'cm' in size_text else pd.NA

            for i in range(len(product_composition)):
                if product_composition[i][0] == 'Size':
                    product_composition[i] = ['Size', size_text]
                    break
            else:
                product_composition.append(['Size', size_text])
                    
            # rename columns DataFrame
            df_composition = pd.DataFrame(product_composition).T
            df_composition.columns = df_composition.iloc[0]

            # delete first row and substitution null values 
            df_composition = df_composition.iloc[1:].fillna( method='ffill' )
                    
            # remove pocket lining, shell and lining 
            df_composition['Composition'] = df_composition['Composition'].replace( 'Pocket lining:', '', regex=True )
            df_composition['Composition'] = df_composition['Composition'].replace( 'Shell:', '', regex=True )
            df_composition['Composition'] = df_composition['Composition'].replace( 'Lining:', '', regex=True )
            
            # garantee the same number of columns
            df_composition = pd.concat( [ df_pattern, df_composition ], axis=0)
                            
            df_composition = df_composition[['Art. No.', 'Composition', 'Fit', 'Product safety', 'Size']]
                            
            # remane columns 
            df_composition.columns = ['product_id', 'composition', 'fit', 'product_safety', 'size']
            df_compositions['product_name'] = product_name        
            df_compositions['product_price'] = product_price
                    
            # keep new columns if it shows up 
            aux = aux + df_composition.columns.tolist()
                            
            # merge data color + data compostition
            df_composition = pd.merge( df_composition, df_color,how='left', on='product_id' )
                                
            # all products
            df_compositions = pd.concat ( [df_compositions, df_composition], axis=0 )
                
    # join showroom data + details
    df_compositions['style_id'] = df_compositions['product_id'].apply( lambda x: x[:-3] )
    df_compositions['color_id'] = df_compositions['product_id'].apply( lambda x: x[-3:] )

    # scrapy datetime
    df_compositions['scrapy_datetime'] = datetime.now().strftime( '%Y-%m-%d %H:%M:%S')

    return df_compositions

## Data Cleaning
def data_cleaning( data_product ):
    # product id
    df_data = data_product.dropna( subset=['product_id'] )

    # product name
    df_data['product_name'] = df_data['product_name'].str.replace( '\n', '' )
    df_data['product_name'] = df_data['product_name'].str.replace( '\r', '' )
    df_data['product_name'] = df_data['product_name'].str.replace( '\t', '' )
    df_data['product_name'] = df_data['product_name'].str.replace( '  ', '' )
    df_data['product_name'] = df_data['product_name'].str.replace( 'freefit®_', '' )
    df_data['product_name'] = df_data['product_name'].str.replace( '_', '' )
    df_data['product_name'] = df_data['product_name'].str.replace( ' ', '_' ).str.lower()
    df_data['product_name'] = df_data['product_name'].str.split('$').str[0]


    # produtc price
    df_data['product_price'] = df_data['product_price'].str.replace( '\n', '' )
    df_data['product_price'] = df_data['product_price'].str.replace( '\r', '' )
    df_data['product_price'] = df_data['product_price'].str.replace( '\t', '' )
    df_data['product_price'] = df_data['product_price'].str.replace( '$', '' )
    df_data['product_price'] = df_data['product_price'].astype( float )

    #  color name 
    df_data['color_name'] = df_data['color_name'].str.replace( ' ', '_').str.lower()      
                                                
    # fit
    df_data['fit'] = df_data['fit'].apply( lambda x: x.replace( ' ', '_').lower() if pd.notnull( x ) else x )

    # size number       # exclui a medida cm
    df_data['size_number'] = df_data['size'].apply( lambda x: re.search( '\d{3}cm', x ).group(0) if pd.notnull( x ) else x)
    df_data['size_number'] = df_data['size'].apply( lambda x: re.search( '\d+', x ).group(0) if pd.notnull( x ) else x)

    # size model 
    df_data['size_model'] = df_data['size'].str.extract( '(\d+/\\d+)' )

    # break composition by comma
    df1 = df_data['composition'].str.split( ',', expand=True ).reset_index(drop=True)


    # cotton | polyester | spandex
    df_ref = pd.DataFrame( index=np.arange( len( data ) ), columns=['cotton', 'polyester', 'spandex'] )

    # ================================== Composition ==================================================

    # --------cotton-----------------
    df_cotton_0 = df1.loc[df1[0].str.contains( 'Cotton', na=True ), 0]
    df_cotton_0.name = 'cotton'

    df_cotton_1 = df1.loc[df1[1].str.contains( 'Cotton', na=True ), 1]
    df_cotton_1.name = 'cotton'

    # combine 
    df_cotton = df_cotton_0.combine_first( df_cotton_1 )

    df_ref = pd.concat( [df_ref, df_cotton], axis=1 )
    df_ref = df_ref.iloc[:, ~df_ref.columns.duplicated( keep='last' )]

    # ----------polyester--------------
    df_polyester_0 = df1.loc[df1[0].str.contains( 'Polyester', na=True ), 0]
    df_polyester_0.name = 'polyester'

    df_polyester_1 = df1.loc[df1[1].str.contains( 'Polyester', na=True ), 1]
    df_polyester_1.name = 'polyester'

    # combine 
    df_polyester = df_polyester_0.combine_first( df_polyester_1 )

    df_ref = pd.concat( [df_ref, df_polyester], axis=1 )
    df_ref = df_ref.iloc[:, ~df_ref.columns.duplicated( keep='last')]
    df_ref['polyester'] = df_ref['polyester'].fillna('Polyester 0%')

    # ----------spandex--------------
    df_spandex_1 = df1.loc[df1[1].str.contains( 'Spandex', na=True ), 1]
    df_spandex_1.name = 'spandex'

    df_spandex_2 = df1.loc[df1[2].str.contains( 'Spandex', na=True ), 2]
    df_spandex_2.name = 'spandex'
                        
    # combine
    df_spandex = df_spandex_1.combine_first( df_spandex_2 )

    df_ref = pd.concat( [df_ref, df_spandex], axis=1 )
    df_ref = df_ref.iloc[:, ~df_ref.columns.duplicated( keep='last')]
    df_ref['spandex'] = df_ref['spandex'].fillna('Spandex 0%')
    
    # join of combine with product_id
    df_aux = pd.concat( [df_data['product_id'].reset_index(drop=True), df_ref], axis=1 )
                        
                
    # format composition data 
    df_aux['cotton']     = df_aux['cotton'].apply( lambda x: int( re.search( '\d+', x ).group(0) ) / 100 if pd.notnull( x ) else x )
    df_aux['polyester']  = df_aux['polyester'].apply( lambda x: int( re.search( '\d+', x ).group(0) ) / 100 if pd.notnull( x ) else x )
    df_aux['spandex']    = df_aux['spandex'].apply( lambda x: int( re.search( '\d+', x ).group(0) ) / 100 if pd.notnull( x ) else x )  
                    
    # final join
    df_aux = df_aux.groupby( 'product_id' ).max().reset_index().fillna( 0 )
    df_data = pd.merge( df_data, df_aux, on='product_id', how='left' )                     
                        
    # drop columns  ##remove after generating the columns size_number e size_model
    df_data = df_data.drop( columns=['size', 'product_safety', 'composition'], axis=1 )

    # drop duplicates 
    df_data = df_data.drop_duplicates()
    
    return df_data

## Data Insert
def data_insert( df_data ):
    data_insert = df_data[[
        'product_id',
        'style_id',
        'color_id',
        'product_name',
        'color_name',
        'fit',
        'product_price',
        'size_number',
        'size_model',
        'cotton',
        'polyester',
        'spandex',
        'scrapy_datetime' 
    ]] 

    # create database connection 
    conn = create_engine( 'sqlite:///database_hm.slqlite', echo=False )

    # data insert 
    data_insert.to_sql( 'vitrine', con=conn, if_exists='append', index=False )

    return None

if __name__ == '__main__':
    # logging
    path = (r'C:\Users\ferki\repos\python_ds_ao_dev\webscraping_hm.py')

    if not os.path.exists( path + 'Logs'):
        os.makedirs( path + 'Logs' )
    
    logging.basicConfig(
        filename = path + 'Logs/webscraping_hm.log',
        level = logging.DEBUG,
        format = '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt = '%Y-%m-%d %H:%M:%S'
    )

    logger = logging.getLogger( 'webscraping_hm' )

    # parameters and constans
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5),AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
    
    # URL 
    url = 'https://www2.hm.com/en_us/men/products/jeans.html'

    # data collection
    data = data_collection( url, headers )
    logger.info( 'data collect done' )
      
    # data collection by product 
    data_product = data_collection_by_product( data, headers )
    logger.info( 'data collection by product done' )

    # data cleaning
    data_product_cleaned = data_cleaning( data_product )
    logger.info( 'data product cleaned done' ) 

    # data insertion
    data_insert( data_product_cleaned )
    logger.info( 'data insertion done' )

