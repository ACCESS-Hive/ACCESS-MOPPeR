# This script adds entries to a database holding post-processing information for access simulations
# 
# Originally written for CMIP5 by Peter Uhe
#
# Adapted for CMIP6 by Chloe Mackallah
# March 2019
## porting to python3: paola.petrelli@utas.edu.au
#
import sqlite3
from optparse import OptionParser
from datetime import datetime
from datetime import timedelta
from datetime import date
import os
import sys
import getpass
import glob
import netCDF4
import csv
import hashlib
import time
import json

exptoprocess = os.environ.get('EXP_TO_PROCESS')
out_dir = os.environ.get('OUT_DIR')
if os.environ.get('MODE').lower() == 'custom':
    mode='custom'
elif os.environ.get('MODE').lower() == 'ccmi':
    mode='ccmi'
else:
    mode='cmip6'

def master_setup(conn):
    cursor=conn.cursor()
    #cursor.execute('drop table if exists file_master')
    #Create the file_master table
    try:
        cursor.execute( '''create table if not exists file_master(
            experiment_id text,
            realization_idx integer,
            initialization_idx integer,
            physics_idx integer,
            forcing_idx integer,
            infile text,
            outpath text,
            file_name text,
            vin text,
            vcmip text,
            cmip_table text,
            frequency text,
            tstart integer,
            tend integer,
            status text, 
            file_size real,
            local_exp_id text,
            calculation text,
            axes_modifier text,
            in_units text,
            positive text,
            timeshot text,
            years text,
            var_notes text,
            cfname text,
            activity_id text,
            institution_id text,
            source_id text,
            grid_label text,
            access_version text,
            json_file_path text,
            reference_date integer,
            version text,
            primary key(local_exp_id,experiment_id,vcmip,cmip_table,realization_idx,initialization_idx,physics_idx,forcing_idx,tstart))''')
    except Exception as e:
        print("Unable to create the APP file_master table.")
        print(e)
        raise e
    conn.commit()

def grids_setup(conn,grid_file):
    cursor=conn.cursor()
    #The grids table describes the number of gridpoints for different classes of variables
    #Delete the grids table then make it again (only necessary if changes are made to its structure) 
    cursor.execute('''drop table if exists grids''')
    try:
        cursor.execute('''create table if not exists grids (
            frequency text,
            dimensions text,
            max_dimensions text,
            gridpoints integer,
            max_file_size_per_year integer,
            max_file_years integer,
            primary key (dimensions,frequency)) ''')
        f=csv.reader(open(grid_file,'r'))
        print(f"using grid file: {grid_file}")
        for line in f:
            if len(line) != 0:
                if line[0][0] != '#':
                    cursor.execute('insert into grids values (?,?,?,?,?,?)', line[0:6])
    except Exception as e:
        print( e, "\n unable to perform operations on grids table")
    conn.commit()

def experiments_setup(conn,exps_file):
    cursor=conn.cursor()
    try:
        cursor.execute('''create table if not exists experiments(
                local_exp_id text,
                local_exp_dir text,
                json_file_path text,
                data_request text,
                reference_date integer,
                start_year integer,
                end_year integer,
                access_version text,
                cmip_exp_id text,
                primary key (local_exp_id,json_file_path,start_year)) ''')
        if mode == 'custom':
            def_hist_data = os.environ.get('HISTORY_DATA')
            def_version = os.environ.get('VERSION')
            def_json = f"{out_dir}/{exptoprocess}.json"
            print(def_json) 
            def_start = os.environ.get('START_YEAR')
            def_end = os.environ.get('END_YEAR')
            if os.environ.get('REFERENCE_YEAR').lower() == 'default':
                def_reference=def_start
            else:
                def_reference = os.environ.get('REFERENCE_YEAR')
            def_dreq = "input_files/dreq/cmvme_all_piControl_3_3.csv"
            def_line=[exptoprocess,def_hist_data,def_json,def_dreq,def_reference,def_start,def_end,def_version,'custom']
            cursor.execute('insert into experiments values (?,?,?,?,?,?,?,?,?)', def_line)
        else:
            f=csv.reader(open(exps_file,'r'))
            for line in f:
                if (len(line) != 0) and (line[0][0] != '#'):
                    #print(line)
                    cursor.execute('insert or replace into experiments values (?,?,?,?,?,?,?,?,?)', line)
    except Exception as e:
        print(e, "\n unable to setup experiments table")
    conn.commit()


def champions_setup(champions_dir,conn):
    cursor=conn.cursor()
    cursor.execute('drop table if exists champions')
    try: 
        cursor.execute( '''create table if not exists champions(
            cmip_table text,            
            cmip_variable text,
            definable text,
            access_variable text,
            file_structure text,
            calculation text,
            in_units text,
            axes_modifier text,
            positive text,
            timeshot text,
            years text,
            notes text,
            cfname text,
            dimension text,
            primary key (cmip_variable,cmip_table))''')
    except:    
        print("Unable to create the champions table.")
    cursor.execute('delete from champions')
    files=os.listdir(champions_dir)
    for table in files:
        if os.path.isdir(f"{champions_dir}/{table}"):
            continue
        if not table.startswith('.'): #hidden file, directory
            try:
                #PP added delimiter "," as separator
                #PP possibly if we should use csv instead of a basic file writer in dreq_mapping.py 
                fcsv = open(f"{champions_dir}/{table}", 'r')
                freader = csv.reader(fcsv, delimiter=',')
                for line in freader:
                    if line[0][0] != '#':
                        row=['N/A']*15
                        for i, item in enumerate(line):
                            row[i+1] = item
                        #cmip_table
                        row[0] = table[:-4]  #champions file with .csv removed        
                        try:
                            cursor.execute('insert into champions values (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ',
                                    row[0:14])
                        except Exception as e:
                            print(f"error inserting line into champions file: {e}\n{row}")
                conn.commit()
            except Exception as e: 
                print(e, table)
                raise
    conn.commit()

def buildFileName(opts):
    #date=datetime.today().strftime('%Y%m%d')
    date=opts['version']
    tString = ''
    frequency = opts['frequency']
    if frequency != 'fx':
        #time values
        st_date = opts['tstart']
        fin_date = opts['tend']
        if opts['timeshot'] in ['mean','clim']:
            #for variables that contain time mean values
            start = str(st_date).zfill(4)
            fin = str(fin_date).zfill(4)
            if frequency == 'yr':
                pass
            elif frequency == 'mon':
                #add month to string
                start = f"{start}01"
                fin = f"{fin}12"
            elif frequency == 'day':
                #add day to string
                start = "{start}0101"
                fin = f"{fin}1231"
            elif frequency == '6hr':
                start = str(st_date).zfill(4)
                fin = str(fin_date+1).zfill(4)
                start = f"'{start}01010300"
                fin = "{fin}12312100"
            elif frequency == '3hr':
                #add minutes to string
                start = f"{start}01010130"
                fin = f"{fin}12312230"
            #hack to fix time for variables where only a single value is used (time invariant)
            if opts['axes_modifier'].find('firsttime') != -1:
                fin = start
        elif opts['timeshot'] == 'inst':
            #snapshot time bounds:
            if frequency in ['3hr', '6hr']:
                start=str(st_date).zfill(4)
                fin=str(fin_date+1).zfill(4)
            else:
                start = str(st_date).zfill(4)
                fin = str(fin_date).zfill(4)
            if frequency == 'mon':
                #add month to string
                start = f"{start}01"
                fin = f"{fin}12"
            elif frequency == '10day':
                #add day to string
                start = f"{start}0111"
                fin = f"{fin}0101"
            elif frequency == 'day':
                #add day to string
                start = f"{start}0101"
                fin = f"{fin}1231"
            elif frequency == '6hr':
                start = f"{start}01010600"
                fin = "{fin}01010000"
            elif frequency == '3hr':
                start = f"{start}01010300"
                fin = f"{fin}01010000"
            else:
                raise Exception('Error creating file name for snapshot data: 6hr or 3hr data expected')
        else:
            raise Exception('Error creating file name: no timeshot in champions table')
        #add time elements into one string        
        tString = f"_{start}-{fin}"
        if opts['timeshot'] == 'clim':
            tString = tString + '-clim'
    # PP probably need to adapt this with python3 string??
    app_out = "{outpath}/"\
    "{activity_id}/"\
    "{institution_id}/"\
    "{source_id}/"\
    "{experiment_id}/"\
    "r{realization_idx}"\
    "i{initialization_idx}"\
    "p{physics_idx}"\
    "f{forcing_idx}/"\
    "{cmip_table}/"\
    "{vcmip}/"\
    "{grid_label}/"\
    "{date}/"\
    "{vcmip}_"\
    "{cmip_table}_"\
    "{source_id}_"\
    "{experiment_id}_"\
    "r{realization_idx}"\
    "i{initialization_idx}"\
    "p{physics_idx}"\
    "f{forcing_idx}_"\
    "{grid_label}"\
    "{tstring}"\
    ".nc".format(date=date, tstring=tString, **opts)
    return app_out
        
#Calculate an estimated output file size (in megabytes)
def computeFileSize(grid_points, frequency, length):  
    #additional amount to take into account space the grid and metadata take up    
    length = float(length)
    # base size is for fixed data 
    #    return grid_points*4/1024/1024.0
    size = grid_points*4.0/1024.0**2
    if frequency == 'yr':
        size = size*length/365
        #return ((length/365)*grid_points*4))/1024.0^2
    elif frequency == 'mon':
        size = size * length * 12/365
        #return length/365*12*grid_points*4/1024/1024.0
    elif frequency == 'day':
        size = size * length
        #return length*grid_points*4/1024/1024.0
    elif frequency == 'monClim':
        size = size * 12
        #return 12*grid_points*4/1024/1024.0
    elif frequency == '6hr':
        size = size * length * 4
        #return length*grid_points*4/1024/1024.0*4
    elif frequency == '3hr':
        size = size * length * 8 
        #return length*grid_points*4/1024/1024.0*8
    elif frequency == '1hr':
        size = size * length * 24 
    elif frequency == '10min':
        size = size * length * 144 
    else:
        size = -1
    return size

def sumFileSizes(conn):
    cursor=conn.cursor()
    cursor.execute('select file_size from file_master')
    sizeList=cursor.fetchall()
    size=0.0
    for s in sizeList:
        size += float(s[0])
    return size

#define the frequency of variable from the cmip table (and variable name (pfull and phalf only))
def tableToFreq(table):
    # PP save it as config file and read it!!!
    dictionary={'3hr': '3hr',
                '6hrLev': '6hr',
                '6hrPlevPt': '6hr',
                '6hrPlev': '6hr',
                'AERday': 'day',
                'AERmon': 'mon',
                'AERmonZ':'mon',
                'Amon':'mon'
    ,'AmonZ':'mon'
    ,'CFday':'day'
    ,'CF3hr':'3hr'
    ,'CFmon':'mon'
    ,'E3hr':'3hr'
    ,'E3hrPt':'3hr'
    ,'Eday':'day'
    ,'EdayZ':'day'
    ,'Aday':'day'
    ,'AdayZ':'day'
    ,'A10dayPt':'10day'
    ,'Efx':'fx'
    ,'Emon':'mon'
    ,'EmonZ':'mon'
    ,'Eyr':'yr'
    ,'ImonGre':'mon'
    ,'ImonAnt':'mon'
    ,'LImon':'mon'
    ,'Lmon':'mon'
    ,'Oclim':'monClim'
    ,'Oday':'day'
    ,'Ofx':'fx'
    ,'Omon':'mon'
    ,'Oyr':'yr'
    ,'SIday':'day'
    ,'SImon':'mon'
    ,'day':'day'
    ,'fx':'fx'}
    return dictionary[table]

#add a row to the file_master database table
#one row specifies the information to produce one output cmip5 file
def addRow(values,cursor):
    try:
        cursor.execute('''insert into file_master
            (experiment_id,realization_idx,initialization_idx,physics_idx,forcing_idx,infile,outpath,file_name,vin,vcmip,cmip_table,
            frequency,tstart,tend,status,file_size,local_exp_id,calculation,axes_modifier,in_units,positive,
            timeshot,years,var_notes,cfname,activity_id,institution_id,source_id,grid_label,access_version,json_file_path,reference_date,version)
        values
            (:experiment_id,:realization_idx,:initialization_idx,:physics_idx,:forcing_idx,:infile,:outpath,:file_name,:vin,:vcmip,:cmip_table,
            :frequency,:tstart,:tend,:status,:file_size,:local_exp_id,:calculation,:axes_modifier,:in_units,:positive,
            :timeshot,:years,:var_notes,:cfname,:activity_id,:institution_id,:source_id,:grid_label,:access_version,:json_file_path,:reference_date,:version)''', values)
    except sqlite3.IntegrityError as e:
        print(f"Row already exists:\n{e}")
    return cursor.lastrowid

#Takes rows (list of rows in champions table)
#opts (list of values to put into file_master row)
#cursor (connection to app.db)
#
#Loops over each row, and adds the values to opts
#Then loops over times in experiment and add rows into file_master table
#(chunks times according to max_file_years in grids table)
#
def populateRows(rows, opts, cursor):
    for champ in rows:
        #defaults    
        #from champions table:
        frequency = tableToFreq(champ[0])
        opts['frequency'] = frequency            
        opts['cmip_table'] = champ[0]
        opts['vcmip'] = champ[1]
        opts['vin'] = champ[3]
        try:
            [a,b] = champ[4].split()
            opts['infile'] = f"{opts['local_exp_dir']}/{a} {opts['local_exp_dir']}/{b}"
        except:    
            opts['infile'] = f"{opts['local_exp_dir']}/{champ[4]}"
        opts['calculation'] = champ[5]
        opts['in_units'] = champ[6]
        opts['axes_modifier'] = champ[7]
        opts['positive'] = champ[8]
        opts['timeshot'] = champ[9]
        opts['years'] = champ[10]
        opts['var_notes'] = champ[11]
        opts['cfname'] = champ[12]
        dimension = champ[13]
        time = opts['exp_start']
        finish = opts['exp_end']
        cursor.execute(f"select max_file_years,gridpoints from grids where dimensions=='{dimension}' and frequency=='{frequency}'")
        #TODO add in check that there is only one value
        try:
            if opts['vcmip'] == 'co2':
                stepyears = 10
                gridpoints = 528960
            else:
                stepyears, gridpoints=cursor.fetchone()
        except:
            print("error: no grid specification for")
            print(f"frequency: {frequency}")
            print(dimension)
            print(opts['vcmip'])
            raise
        #loop over times
        while (time <= finish):        
            newtime = min(time+stepyears-1,finish)
            stepDays = (datetime(newtime+1,1,1)-datetime(time,1,1)).days
            opts['tstart'] = time     
            opts['tend'] = newtime 
            opts['file_size'] = computeFileSize(gridpoints,frequency,stepDays)
            opts['file_name'] = buildFileName(opts)
            rowid = addRow(opts, cursor)
            time = newtime+1

#populate the database for variables that are requested for all times for all experiments
def populate_unlimited(cursor,opts):
    #monthly, daily unlimited except cable or moses specific diagnostics
    cursor.execute("select * from champions where definable=='yes'")
    rows = cursor.fetchall()
    #populateRows(cursor.fetchall(), opts, cursor)
    populateRows(rows, opts, cursor)

#choose grid file to determine chunking, based on access_version
def grid_file_choose(conn):
    cursor = conn.cursor()
    cursor.execute(f"select * from experiments where local_exp_id=='{exptoprocess}'")
    for exp in cursor.fetchall():
        access_version = exp[7]
    if access_version.find('OM2') != -1:
        if access_version.find('025') != -1:
            grid_file = f"{sys.path[0]}/../input_files/grids_om2-025.csv"
        else: 
            grid_file = f"{sys.path[0]}/../input_files/grids_om2.csv"
    else:
        grid_file = f"{sys.path[0]}/../input_files/grids.csv"
    return grid_file

#
#
#main script to populate the file_master table
#
def populate(conn):
    cursor = conn.cursor()
    #defaults
    opts = dict()
    opts['status'] = 'unprocessed'
    #get experiment information
    cursor.execute(f"select * from experiments where local_exp_id=='{exptoprocess}'")
    #loop over different experiments
    for exp in cursor.fetchall():
        opts['json_file_path'] = exp[2]
        json_dict = read_json_file(opts['json_file_path'])
        #Experiment Details:
        opts['outpath'] = json_dict['outpath']
        opts['experiment_id'] = json_dict['experiment_id']
        opts['realization_idx'] = json_dict['realization_index']
        opts['initialization_idx'] = json_dict['initialization_index']
        opts['physics_idx'] = json_dict['physics_index']
        opts['forcing_idx'] = json_dict['forcing_index']
        opts['activity_id'] = json_dict['activity_id']
        opts['institution_id'] = json_dict['institution_id']
        opts['source_id'] = json_dict['source_id']
        opts['grid_label'] = json_dict['grid_label']
        opts['version'] = json_dict.get('version', datetime.today().strftime('%Y%m%d'))
        opts['local_exp_id'] = exp[0]
        opts['local_exp_dir'] = exp[1]
        opts['reference_date'] = exp[4]
        opts['exp_start'] = exp[5]
        opts['exp_end'] = exp[6]
        opts['access_version'] = exp[7]
        opts['cmip_exp_id'] = exp[8]
        print(f"found local experiment: {opts['local_exp_id']}")
        populate_unlimited(cursor,opts)
        conn.commit()


def read_json_file(path):
    """Read the cmip json file (containing experiment information) 
    into a python dictionary
    """
    with open(path,'r') as f:
        json_dict=json.load(f)
    f.close()
    return json_dict


def create_database_updater():
    database_updater = f"{out_dir}/database_updater.py"
    with open(database_updater,'w+') as dbu:
        dbu.write('import os\n'\
            'import sqlite3\n'\
            'database=os.environ.get("DATABASE")\n'\
            'print(database)\n'\
            'out_dir=os.environ.get("OUT_DIR")\n'\
            'conn=sqlite3.connect(database)\n'\
            'conn.text_factory=str\n'\
            'cursor=conn.cursor()\n'\
            'def setStatus(status,rowid):\n'\
            '    cursor.execute("update file_master set status=? where ROWID=?",[status,rowid])\n'\
            #'    print "set status: ",status\n'\
            '    conn.commit()\n'\
            'print("updating database...")\n')
    dbu.close()


def count_rows(conn):
    cursor=conn.cursor()
    #cursor.execute(f"select * from file_master where status=='unprocessed' and local_exp_id=='{exptoprocess}'")
    cursor.execute(f"select * from file_master")
    rows = cursor.fetchall()
    print(f"Number of rows: {len(rows)}")
    #for row in rows:
    #    print(row)
    database_count=f"{out_dir}/database_count.txt"
    with open(database_count,'w') as dbc:
        dbc.write(str(len(rows)))
    dbc.close()


def main():
    print("\nstarting database_manager...")
    #Global variable:
    #set champions tables directory from environment variable
    champions_dir = os.environ.get('VARIABLE_MAPS')
    if not champions_dir:
        sys.exit('missing variable maps')
    print(f"champions directory: {champions_dir}")
    #set Experiments table from environment variable
    exp_table = os.environ.get('EXPERIMENTS_TABLE')
    #Set default experiments table
    if not exp_table:
        print("no experiments table specified, using default")
        exp_table = f"{sys.path[0]}/../input_files/experiments.csv"
    print(f"experiments table: {exp_table}")
    #Create a connection to the database.    
    #get database from environment var
    database = os.environ.get('DATABASE')
    if not database:
        sys.exit('missing database')
    print(f"creating & using database: {database}")
    conn = sqlite3.connect(database)
    conn.text_factory = str
    #setup database tables
    master_setup(conn)
    experiments_setup(conn,exp_table)
    grid_file = grid_file_choose(conn)
    grids_setup(conn,grid_file)
    champions_setup(champions_dir,conn)
    populate(conn)
    print('past populate')
    create_database_updater()
    count_rows(conn)
    print(f"max total file size is: {sumFileSizes(conn)/1024} GB")

if __name__ == "__main__":
    main()
