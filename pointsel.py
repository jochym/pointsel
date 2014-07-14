#!/usr/bin/env python

from __future__ import division
from numpy import array
import numpy as np
import matplotlib.pyplot as plt

def readData(fn, skip=1):
    '''
    Read and translate the data from the file named fn.
    The data is returned as an array of rows x cols 
    in the second member of the returned list.
    The first skip (default 1) line are skipped.
    If the skip is >0 the contents of this line is returned
    in the first member of the returned list as a list
    of labels (split on ;).
    '''
    df=open(fn).readlines()
    #print(df[0].strip())
    # The translation replaces ; and , by space and dot.
    if skip>0 :
        lbl=df[0].strip().split(';')
    else :
        lbl=None
    return [lbl, array([
                    map(float,
                        ln.replace(';',' ').replace(',','.').split()) 
                    for ln in df[skip:]]).T]

def displayData(dat, lbl=None, cols=(0,1)):
    '''
    Display the points in the cols of the dat array.
    The axes are lebeled with labels from the lbl parameter.
    The lbl must contain a list of labels for columns.
    '''
    plt.plot(dat[cols[0]],dat[cols[1]],',')
    ax=plt.gca()
    if lbl :
        plt.xlabel(lbl[cols[0]])
        plt.ylabel(lbl[cols[1]])
    plt.show()

if __name__ == '__main__':

    # Example data
    datfn='data/A339-SiC-560-1-SiC-WDS.txt'
    dat=readData(datfn)
    displayData(dat[1],dat[0])
