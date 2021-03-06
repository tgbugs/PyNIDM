#!/usr/bin/env python
#**************************************************************************************
#**************************************************************************************
#  CSV2NIDM.py
#  License: GPL
#**************************************************************************************
#**************************************************************************************
# Date: 01-19-18                 Coded by: David Keator (dbkeator@gmail.com)
# Filename: CSV2NIDM.py
#
# Program description:  This program will load in a CSV file and iterate over the header
# variable names performing an elastic search of https://scicrunch.org/ for NIDM-ReproNim
# tagged terms that fuzzy match the variable names.  The user will then interactively pick
# a term to associate with the variable name.  The resulting annotated CSV data will
# then be written to a NIDM data file.
#
#**************************************************************************************
# Development environment: Python - PyCharm IDE
#
#**************************************************************************************
# System requirements:  Python 3.X
# Libraries: pybids, numpy, matplotlib, pandas, scipy, math, dateutil, datetime,argparse,
# os,sys,getopt,csv
#**************************************************************************************
# Start date: 01-19-18
# Update history:
# DATE            MODIFICATION				Who
#
#
#**************************************************************************************
# Programmer comments:
#
#
#**************************************************************************************
#**************************************************************************************

import os,sys
from nidm.experiment import Project,Session,AssessmentAcquisition,AssessmentObject
from nidm.core import Constants
from nidm.experiment.Utils import read_nidm, map_variables_to_terms, add_attributes_with_cde, addGitAnnexSources
from argparse import ArgumentParser
from os.path import  dirname, join, splitext,basename
import json
import pandas as pd
from rdflib import Graph,URIRef,RDF,Literal
from io import StringIO
from shutil import copy2
from nidm.core.Constants import DD
import logging
import csv


#def createDialogBox(search_results):
#class NewListbox(tk.Listbox):

#    def autowidth(self, maxwidth=100):
#        autowidth(self, maxwidth)


#def autowidth(list, maxwidth=100):
#    f = font.Font(font=list.cget("font"))
#    pixels = 0
#    for item in list.get(0, "end"):
#        pixels = max(pixels, f.measure(item))
#    # bump listbox size until all entries fit
#    pixels = pixels + 10
#    width = int(list.cget("width"))
#    for w in range(0, maxwidth+1, 5):
#        if list.winfo_reqwidth() >= pixels:
#            break
#        list.config(width=width+w)





def main(argv):
    parser = ArgumentParser(description='This program will load in a CSV file and iterate over the header \
     variable names performing an elastic search of https://scicrunch.org/ for NIDM-ReproNim \
     tagged terms that fuzzy match the variable names.  The user will then interactively pick \
     a term to associate with the variable name.  The resulting annotated CSV data will \
     then be written to a NIDM data file.  Note, you must obtain an API key to Interlex by signing up \
     for an account at scicrunch.org then going to My Account and API Keys.  Then set the environment \
     variable INTERLEX_API_KEY with your key.')

    parser.add_argument('-csv', dest='csv_file', required=True, help="Path to CSV file to convert")
    # parser.add_argument('-ilxkey', dest='key', required=True, help="Interlex/SciCrunch API key to use for query")
    parser.add_argument('-json_map', dest='json_map',required=False,help="User-suppled JSON file containing variable-term mappings.")
    parser.add_argument('-nidm', dest='nidm_file', required=False, help="Optional NIDM file to add CSV->NIDM converted graph to")
    # parser.add_argument('-owl', action='store_true', required=False, help='Optionally searches NIDM OWL files...internet connection required')
    # parser.add_argument('-png', action='store_true', required=False, help='Optional flag, when set a PNG image file of RDF graph will be produced')
    # parser.add_argument('-jsonld', action='store_true', required=False, help='Optional flag, when set NIDM files are saved as JSON-LD instead of TURTLE')
    parser.add_argument('-log','--log', dest='logfile',required=False, default=None, help="directory to save log file. Log file name is csv2nidm_[arg.csv_file].log")
    parser.add_argument('-out', dest='output_file', required=True, help="Filename to save NIDM file")
    args = parser.parse_args()



    #open CSV file and load into
    df = pd.read_csv(args.csv_file)
    #temp = csv.reader(args.csv_file)
    #df = pd.DataFrame(temp)

    #maps variables in CSV file to terms
    #if args.owl is not False:
    #    column_to_terms = map_variables_to_terms(df=df, apikey=args.key, directory=dirname(args.output_file), output_file=args.output_file, json_file=args.json_map, owl_file=args.owl)
    #else:
    column_to_terms, cde = map_variables_to_terms(df=df,  assessment_name=basename(args.csv_file),directory=dirname(args.output_file), output_file=args.output_file, json_file=args.json_map)


    if args.logfile is not None:
        logging.basicConfig(filename=join(args.logfile,'csv2nidm_' + os.path.splitext(os.path.basename(args.csv_file))[0] + '.log'), level=logging.DEBUG)
        # add some logging info
        logging.info("csv2nidm %s" %args)


    #If user has added an existing NIDM file as a command line parameter then add to existing file for subjects who exist in the NIDM file
    if args.nidm_file:
        print("Adding to NIDM file...")
        #read in NIDM file
        project = read_nidm(args.nidm_file)
        #get list of session objects
        session_objs=project.get_sessions()

        #look at column_to_terms dictionary for NIDM URL for subject id  (Constants.NIDM_SUBJECTID)
        id_field=None
        for key, value in column_to_terms.items():
            if Constants.NIDM_SUBJECTID._str == column_to_terms[key]['label']:
                key_tuple = eval(key)
                #id_field=key
                id_field = key_tuple.variable
                #make sure id_field is a string for zero-padded subject ids
                #re-read data file with constraint that key field is read as string
                df = pd.read_csv(args.csv_file,dtype={id_field : str})
                break

        #if we couldn't find a subject ID field in column_to_terms, ask user
        if id_field is None:
            option=1
            for column in df.columns:
                print("%d: %s" %(option,column))
                option=option+1
            selection=input("Please select the subject ID field from the list above: ")
            id_field=df.columns[int(selection)-1]
            #make sure id_field is a string for zero-padded subject ids
            #re-read data file with constraint that key field is read as string
            df = pd.read_csv(args.csv_file,dtype={id_field : str})



        #use RDFLib here for temporary graph making query easier
        rdf_graph = Graph()
        rdf_graph.parse(source=StringIO(project.serializeTurtle()),format='turtle')

        print("Querying for existing participants in NIDM graph....")
        #find subject ids and sessions in NIDM document
        query = """SELECT DISTINCT ?session ?nidm_subj_id ?agent
                    WHERE {
                        ?activity prov:wasAssociatedWith ?agent ;
                            dct:isPartOf ?session  .
                        ?agent rdf:type prov:Agent ;
                            ndar:src_subject_id ?nidm_subj_id .
                    }"""
        #print(query)
        qres = rdf_graph.query(query)


        for row in qres:
            logging.info("found existing participant %s \t %s" %(row[0],row[1]))
            #find row in CSV file with subject id matching agent from NIDM file

            #csv_row = df.loc[df[id_field]==type(df[id_field][0])(row[1])]
            #find row in CSV file with matching subject id to the agent in the NIDM file
            #be carefull about data types...simply type-change dataframe subject id column and query to strings.
            #here we're removing the leading 0's from IDs because pandas.read_csv strips those unless you know ahead of
            #time which column is the subject id....
            csv_row = df.loc[df[id_field].astype('str').str.contains(str(row[1]).lstrip("0"))]

            #if there was data about this subject in the NIDM file already (i.e. an agent already exists with this subject id)
            #then add this CSV assessment data to NIDM file, else skip it....
            if (not (len(csv_row.index)==0)):

                #NIDM document sesssion uuid
                session_uuid = row[0]

                #temporary list of string-based URIs of session objects from API
                temp = [o.identifier._uri for o in session_objs]
                #get session object from existing NIDM file that is associated with a specific subject id
                #nidm_session = (i for i,x in enumerate([o.identifier._uri for o in session_objs]) if x == str(session_uuid))
                nidm_session = session_objs[temp.index(str(session_uuid))]
                #for nidm_session in session_objs:
                #    if nidm_session.identifier._uri == str(session_uuid):
                #add an assessment acquisition for the phenotype data to session and associate with agent
                acq=AssessmentAcquisition(session=nidm_session)
                #add acquisition entity for assessment
                acq_entity = AssessmentObject(acquisition=acq)
                #add qualified association with existing agent
                acq.add_qualified_association(person=row[2],role=Constants.NIDM_PARTICIPANT)

                # add git-annex info if exists
                num_sources = addGitAnnexSources(obj=acq_entity,filepath=args.csv_file,bids_root=dirname(args.csv_file))
                # if there aren't any git annex sources then just store the local directory information
                if num_sources == 0:
                    # WIP: add absolute location of BIDS directory on disk for later finding of files
                    acq_entity.add_attributes({Constants.PROV['Location']:"file:/" + args.csv_file})

                # store file to acq_entity
                acq_entity.add_attributes({Constants.NIDM_FILENAME:basename(args.csv_file)})

                #store other data from row with columns_to_term mappings
                for row_variable in csv_row:
                    #check if row_variable is subject id, if so skip it
                    if row_variable==id_field:
                        continue
                    else:
                        if not csv_row[row_variable].values[0]:
                            continue


                        add_attributes_with_cde(acq_entity, cde, row_variable, csv_row[row_variable].values[0])



                continue

        print ("Adding CDEs to graph....")
        # convert to rdflib Graph and add CDEs
        rdf_graph = Graph()
        rdf_graph.parse(source=StringIO(project.serializeTurtle()),format='turtle')
        rdf_graph = rdf_graph + cde

        print("Backing up original NIDM file...")
        copy2(src=args.nidm_file,dst=args.nidm_file+".bak")
        print("Writing NIDM file....")
        rdf_graph.serialize(destination=args.nidm_file,format='turtle')




        #serialize NIDM file
        # with open(args.nidm_file,'w') as f:
        #    print("Writing NIDM file...")
        #    if args.jsonld:
        #        f.write(project.serializeJSONLD())
        #    else:
        #        f.write(project.serializeTurtle())
        #
        #    if args.png:
        #        project.save_DotGraph(str(args.nidm_file + ".png"), format="png")



    else:
        print("Creating NIDM file...")
        #If user did not choose to add this data to an existing NIDM file then create a new one for the CSV data
        #create empty project
        project=Project()

        #simply add name of file to project since we don't know anything about it
        project.add_attributes({Constants.NIDM_FILENAME:args.csv_file})


        #look at column_to_terms dictionary for NIDM URL for subject id  (Constants.NIDM_SUBJECTID)
        id_field=None
        for key, value in column_to_terms.items():
            if Constants.NIDM_SUBJECTID._str == column_to_terms[key]['label']:
                key_tuple = eval(key)
                id_field=key_tuple.variable
                #make sure id_field is a string for zero-padded subject ids
                #re-read data file with constraint that key field is read as string
                df = pd.read_csv(args.csv_file,dtype={id_field : str})
                break

        #if we couldn't find a subject ID field in column_to_terms, ask user
        if id_field is None:
            option=1
            for column in df.columns:
                print("%d: %s" %(option,column))
                option=option+1
            selection=input("Please select the subject ID field from the list above: ")
            id_field=df.columns[int(selection)-1]
            #make sure id_field is a string for zero-padded subject ids
            #re-read data file with constraint that key field is read as string
            df = pd.read_csv(args.csv_file,dtype={id_field : str})


        #iterate over rows and store in NIDM file
        for csv_index, csv_row in df.iterrows():
            #create a session object
            session=Session(project)

            #create and acquisition activity and entity
            acq=AssessmentAcquisition(session)
            acq_entity=AssessmentObject(acq)

            #create prov:Agent for subject
            #acq.add_person(attributes=({Constants.NIDM_SUBJECTID:row['participant_id']}))

            # add git-annex info if exists
            num_sources = addGitAnnexSources(obj=acq_entity,filepath=args.csv_file,bids_root=os.path.dirname(args.csv_file))
            # if there aren't any git annex sources then just store the local directory information
            if num_sources == 0:
                # WIP: add absolute location of BIDS directory on disk for later finding of files
                acq_entity.add_attributes({Constants.PROV['Location']:"file:/" + args.csv_file})

            # store file to acq_entity
            acq_entity.add_attributes({Constants.NIDM_FILENAME : basename(args.csv_file)})


            #store other data from row with columns_to_term mappings
            for row_variable,row_data in csv_row.iteritems():
                if not row_data:
                    continue

                #check if row_variable is subject id, if so skip it
                if row_variable==id_field:
                    #add qualified association with person
                    acq.add_qualified_association(person= acq.add_person(attributes=({Constants.NIDM_SUBJECTID:str(row_data)})),role=Constants.NIDM_PARTICIPANT)

                    continue
                else:
                    add_attributes_with_cde(acq_entity, cde, row_variable, row_data)

                    #print(project.serializeTurtle())

        # convert to rdflib Graph and add CDEs
        rdf_graph = Graph()
        rdf_graph.parse(source=StringIO(project.serializeTurtle()),format='turtle')
        rdf_graph = rdf_graph + cde

        print("Writing NIDM file....")
        rdf_graph.serialize(destination=args.output_file,format='turtle')



if __name__ == "__main__":
   main(sys.argv[1:])
