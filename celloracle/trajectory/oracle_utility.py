from copy import deepcopy
import warnings
import logging
import numpy as np

import pandas as pd
import os
from numba import jit
import scanpy as sc

from ..utility import intersect

import warnings

#########################
### utility functions ###
#########################


#################################################
### functions for data handling with anndata  ###
#################################################
def _check_color_information_and_create_if_not_found(adata, cluster_column_name, embedding_name):
    if f"{cluster_column_name}_colors" in adata.uns.keys():
        pass
    else:
        message = f"Color information for the {cluster_column_name} is not found in the anndata. CellOracle is plotting the clustering data, {cluster_column_name}, to create color data."
        warnings.warn(message, UserWarning)
        sc.pl.embedding(adata, basis=embedding_name, color=cluster_column_name)

def _linklist2dict(linklist):
    dic = {}
    tmp = linklist.set_index("target")
    for i in tmp.index.unique():
        dic[i] = tmp.loc[i][["source"]].values.flatten()
    return dic

def _adata_to_matrix(adata, layer_name, transpose=True):
    """
    Extract an numpy array from adata and returns as numpy matrix.

    Args:
        adata (anndata): anndata

        layer_name (str): name of layer in anndata

        trabspose (bool) : if True, it returns transposed array.

    Returns:
        2d numpy array: numpy array
    """
    if isinstance(adata.layers[layer_name], np.ndarray):
        matrix = adata.layers[layer_name].copy()
    else:
        matrix = adata.layers[layer_name].todense().A.copy()

    if transpose:
        matrix = matrix.transpose()

    return matrix.copy(order="C")


def _adata_to_df(adata, layer_name, transpose=False):
    """
    Extract an numpy array from adata and returns as pandas DataFrane with cell names and gene names.

    Args:
        adata (anndata): anndata

        layer_name (str): name of layer in anndata

        trabspose (bool) : if True, it returns transposed array.

    Returns:
        pandas.DataFrame: data frame (cells x genes (if transpose == False))
    """
    array = _adata_to_matrix(adata, layer_name, transpose=False)
    df = pd.DataFrame(array, columns=adata.var.index.values, index=adata.obs.index.values)

    if transpose:
        df = df.transpose()
    return df

def _adata_to_color_dict(adata, cluster_use):
    """
    Extract color information from adata and returns as dictionary.

    Args:
        adata (anndata): anndata

        cluster_use (str): column name in anndata.obs

    Returns:
        dictionary: python dictionary, key is cluster name, value is clor name
    """
    color_dict = {}
    for i,j in enumerate(adata.obs[cluster_use].cat.categories):
        color_dict[j] = adata.uns[f"{cluster_use}_colors"][i]
    return color_dict



def _get_clustercolor_from_anndata(adata, cluster_name, return_as):
    """
    Extract clor information from adata and returns as palette (pandas data frame) or dictionary.

    Args:
        adata (anndata): anndata

        cluster_name (str): cluster name in anndata.obs

        return_as (str) : "palette" or "dict"

    Returns:
        2d numpy array: numpy array
    """
        # return_as: "palette" or "dict"
    def float2rgb8bit(x):
        x = (x*255).astype("int")
        x = tuple(x)

        return x

    def rgb2hex(rgb):
        return '#%02x%02x%02x' % rgb

    def float2hex(x):
        x = float2rgb8bit(x)
        x = rgb2hex(x)
        return x

    def hex2rgb(c):
        return (int(c[1:3],16),int(c[3:5],16),int(c[5:7],16), 255)

    def get_palette(adata, cname):
        c = [i.upper() for i in adata.uns[f"{cname}_colors"]]
        #c = sns.cubehelix_palette(24)
        """
        col = adata.obs[cname].unique()
        col = list(col)
        col.sort()
        """
        try:
            col = adata.obs[cname].cat.categories
            pal = pd.DataFrame({"palette": c}, index=col)
        except:
            col = adata.obs[cname].cat.categories
            c = c[:len(col)]
            pal = pd.DataFrame({"palette": c}, index=col)
        return pal

    pal = get_palette(adata, cluster_name)
    if return_as=="palette":
        return pal
    elif return_as=="dict":
        col_dict = {}
        for i in pal.index:
            col_dict[i] = np.array(hex2rgb(pal.loc[i, "palette"]))/255
        return col_dict
    else:
        raise ValueErroe("return_as")
    return 0

@jit(nopython=True)
def _numba_random_seed(value: int) -> None:
    """Same as np.random.seed but for numba"""
    np.random.seed(value)

def _decompose_TFdict(TFdict):
    """
    Args:
        TFdict (dict): Key is target gene, Value is a list of regulatory gene of this target.

    Return:
        (list, list): list of all target gene in the TFdict and list of regulatory gene in the TFdict.
    """

    all_regulatory_genes_in_TFdict = []
    for val in TFdict.values():
        all_regulatory_genes_in_TFdict += list(val)
    all_regulatory_genes_in_TFdict = list(np.unique(all_regulatory_genes_in_TFdict))

    all_target_genes_in_TFdict = list(TFdict.keys())

    return all_target_genes_in_TFdict, all_regulatory_genes_in_TFdict


def _is_perturb_condition_valid(adata, goi, value, safe_range_fold=2):

    """
    Check the input perturb condition is within the safe range.
    Args:
        adata (anndata): scRNA-seq data
        goi (str): Gene of interest
        value (str): Perturb condition input value
        safe_range_fold (float or int): Fold change value.
    Returns:
        Bool

    """
    actual_values = sc.get.obs_df(adata, keys=[goi], layer="imputed_count").values
    min_ = actual_values.min()
    max_ = actual_values.max()
    range_ = max_ - min_

    upper_limit = range_ * (safe_range_fold -1) + max_

    if value <= upper_limit:
        return True
    else:
        return False
