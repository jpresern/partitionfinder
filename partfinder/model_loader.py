# Copyright (C) 2012 Robert Lanfear and Brett Calcott
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details. You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# PartitionFinder also includes the PhyML program, the RAxML program, and the
# PyParsing library, all of which are protected by their own licenses and
# conditions, using PartitionFinder implies that you agree with those licences
# and conditions as well.

import logtools
import pandas as pd
import os
import collections

log = logtools.get_logger()
from util import PartitionFinderError

_available_lists = ["all_dna", # all DNA models, excluding those with base frequencies estimated by ML
                    "all_dnax", # all DNA models, including those with base frequencies estimated by ML
                    "all_proteinx", # all protein models, excluding those with base frequencies estimated by ML
                    "all_protein", # all protein models, including those with base frequencies estimated by ML
                    "all", # all models, excluding those with base frequencies estimated by ML
                    "allx", # all models, including those with base frequencies estimated by ML
                    "beast", # all models available in BEAST 2
                    "mrbayes", # all models available in MrBayes 3.3
                    "just_gamma", # only models with +G (not + nothing, and not +I+G)
                    "just_gammaI", # only modles with +I+G
                    "protein_gamma", # only protein models with +G (included for back-compatibility only; 'just_gamma' is equivalent now)
                    "protein_gammaI", # only protein models with +I+G (included for back-compatibility only; 'just_gammaI' is equivalent now)
                    "raxml" # all models in raxml (included for back-compatibiligy only; 'all' is equivalent now)
                    ]


def load_models(the_config):
    HERE = os.path.abspath(os.path.dirname(__file__))
    all_models = pd.read_csv(os.path.join(HERE, 'models.csv'))

    # determine available models based on datatype and phylogeny program
    the_config.available_models = get_available_models(all_models, the_config)

    # check user models will run
    parse_user_models(the_config)

    log.info("This analysis will use the following %d models of molecular evolution"
             % len(the_config.models))
    log.info("%s" % ', '.join(the_config.models))


def get_available_models(all_models, the_config):
    # from the list of all models, which ones could we actually run
    if the_config.phylogeny_program == 'phyml':
        available_models = all_models[pd.notnull(all_models.phyml_commandline)]
    elif the_config.phylogeny_program == 'raxml':
        available_models = all_models[pd.notnull(all_models.raxml_commandline)]

    if the_config.datatype == 'DNA':
        available_models = available_models.query("datatype=='DNA'")
    elif the_config.datatype == 'protein':
        available_models = available_models.query("datatype=='protein'")
    elif the_config.datatype == 'morphology':
        available_models = available_models.query("datatype=='morphology'")
    else:
        log.error("Unknown datatype '%s'" % the_config.datatype)

    if len(available_models) == 0:
        log.error("""Phylogeny program '%s' does not implement any models that deal 
                  with %s data. Please check and try again. For morphological data,
                  use RAxML (--raxml at the commandline)""" % 
                  (the_config.phylogeny_program, the_config.datatype))
        raise PartitionFinderError

    return available_models

def parse_user_models(the_config):

    # this will tell us if they entered any lists or models we can't use
    check_all_models_and_lists(the_config)

    check_for_duplicates(the_config.models)

    mod_list = check_model_lists(the_config.models)

    if mod_list:
        expand_model_list(the_config)

    # final check on models
    check_all_models(the_config)

def check_all_models(the_config):
    # everything has to be a model in the_config.available_models
    models = the_config.models
    allowed = set(the_config.available_models.name)

    problems = set(models).difference(allowed)

    if problems:
        log.error("""'%s' is/are not a valid model(s) for phylogeny program %s
                  and data type %s, please check and try again""" 
                  %(', '.join(problems), the_config.phylogeny_program, the_config.datatype))
        log.info("""If you are unsure which models are available, or why a model you think 
                 should work does not, please check the manual and the models.csv file 
                 (located in the /partfinder folder) for more information.""")
        raise PartitionFinderError

def check_all_models_and_lists(the_config):
    # everything has to be either a model in the_config.available_models
    # OR a valid option from the _available_models
    models = the_config.models
    allowed = set(_available_lists).union(set(the_config.available_models.name))

    problems = set(models).difference(allowed)

    if problems:
        log.error("""'%s' is/are not a valid model(s) or lists of models 
                  for phylogeny program %s and data type %s, 
                  please check and try again.""" 
                  %(', '.join(problems), the_config.phylogeny_program, the_config.datatype))

        log.info("""If you are unsure which models are available, or why a model you think 
                 should work does not, please check the manual and the models.csv file 
                 (located in the /partfinder folder) for more information.""")
        raise PartitionFinderError
        

def check_model_lists(models):

    mod_lists = set(models).intersection(set(_available_lists))

    if mod_lists and len(models)>1:
        log.error("""If you use a model list (you used '%s') you can only
                  specify a single list, and no other lists or models. Please 
                  check and try again.""" % ', '.join(mod_lists))
        raise PartitionFinderError

    return mod_lists


def expand_model_list(the_config):

    # by this point, we know that mod_list is a list of length 1
    mod_list = the_config.models[0]

    the_config.models = list(the_config.available_models.query("%s==1" % mod_list).name)

    if len(the_config.models)<1:
        log.error("""The model list '%s' is not a compatible with 
                  for phylogeny program %s and data type %s. 
                  There are no models in that list which work with 
                  that combination of program and data type. Please check and try again.""" 
                  %(mod_list, the_config.phylogeny_program, the_config.datatype))
        raise PartitionFinderError


def check_for_duplicates(models):
    # model lists shouldn't contain duplicated models
    duplicates = [x for x, y in collections.Counter(models).items() if y > 1]
    if len(duplicates)>0:
        log.error("""There was a problem loading your list of models,
                  the following models seem to be duplicated: %s"""
                  % duplicates)
        raise PartitionFinderError
