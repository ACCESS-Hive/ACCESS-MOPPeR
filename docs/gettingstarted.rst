Starting with MOPPeR
====================

A typical workflow to post-process a ACCESS or UM model output requires 3 steps.

Step1: get a list of variables from the raw output
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash
   mopdb varlist -i <path-to-raw-output> -d <date-pattern>
   mopdb varlist -i /scratch/.. -d 20120101 

`mopdb varlist` will output one or more files `csv` files with a detailed list of variables, one list for each pattern of output files.
See .. for an example

The <date-pattern> argument is used to reduced the number of files to check. The tool will recognise anyway a repeated pattern and only add a list of variable for the same pattern once.

 
Step2: create a template for a mapping file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash
   mopdb template -i <varlist.csv> -v <access-version> -a <alias>
   mopdb varlist -i myexperiment.csv -v AUS2200 - a exp22 

`mopdb template` takes as input:
 * the output/s of `varlist` - To get one template for the all variable concatenate the output on `varlist` into one file first.
 * the access version to use as preferred
 * an optional alias if omitted the varlist filename will be used. From the example `map_exp22.csv` or `map_varlist.csv` if omitted.

The output is one csv file with again a list of all the variables passed but with added the relcontaining the mappings from raw output to cmip style variables. This includes variables that can be potentially calculated with the listed fields. This file should be considered only a template (hence the name) as the tool will make his best to match the raw output to the mappings stored in the access.db database distributed with the repository.
To see more on what to do should your experiment use a new configuration which is substantially different from what is available see relevant .... 

.. warning:: 
   Always check that the resulting template is mapping the variables correctly. This is particularly true for derived variables. Comment lines are inserted to give some information on what assumptions were done for each group of mappings.

Step3: Set up the working environment 
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash
   mop -i <conf_exp.yaml> setup
   mopdb  -i conf_flood22.yaml setup 

`mop setup` takes as input a yaml configuration file for the experiment based on the provided ACDD_conf.yaml for custom mode and CMIP6_conf.yaml for CMIP6 mode.


.. note::
   These two configurations are based on CMOR Controlled Vocabularies currently available with the repository. 
   A user can define and set their own CV and then modifiy the configuration yaml file correspondingly. However, there are CMOR hardcoded limitations, see the `CMOR section <Understanding the CMOR3 structure>`_ for more information.


`mop setup` sets up the working environment by default in 

.. code::
   /scratch/<project>/<userid>/MOPPeR-Output/

This includes the mopper_job.sh job to submit to the queue.  
In fact if `test` is set to False in the configuration file the job is automatically submitted. 

.. note::
   `mop run` is used to execute the post-processing and it is called in mopper_job.sh. 
   It takes a final experiment configuration yaml file generated in the same setup step to finalise the run settings.  

