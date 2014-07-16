#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014 by Paweł T. Jochym <pawel.jochym@ifj.edu.pl>
# This code is licensed under GPL v2 or later.
# The oryginal repo is at: https://github.com/jochym/pointsel
#

from __future__ import division, print_function
from numpy import array
import numpy as np
import sys
import matplotlib
import wxversion
wxversion.ensureMinimal('2.8')
matplotlib.use('WXAgg')

from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wx import NavigationToolbar2Wx

from matplotlib.figure import Figure

import wx
import matplotlib as mpl
import matplotlib.pyplot as plt





class CanvasFrame(wx.Frame):

    def __init__(self):
        wx.Frame.__init__(self,None,-1,
                         'CanvasFrame',size=(800,600))

        self.SetBackgroundColour(wx.NamedColour("WHITE"))

        self.figure = Figure()
        self.axes = self.figure.add_subplot(111)

        try :
            self.datfn=sys.argv[1]
        except IndexError :
            # Example data
            self.datfn='data/A339-SiC-560-1-SiC-WDS.txt'

        try :
            self.dat=self.readData(self.datfn)
        except IOError :
            print('Warning: Cannot open file ', self.datfn)
            self.dat=[['',''],array([[],[]])]

        self.displayData(self.dat[1],self.dat[0])

        self.canvas = FigureCanvas(self, -1, self.figure)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.canvas, 1, wx.LEFT | wx.TOP | wx.GROW)
        self.SetSizer(self.sizer)
        self.Fit()

        self.add_toolbar()  # comment this out for no toolbar

    def readData(self, fn, skip=1):
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

    def displayData(self, dat, lbl=None, cols=(0,1)):
        '''
        Display the points in the cols of the dat array.
        The axes are lebeled with labels from the lbl parameter.
        The lbl must contain a list of labels for columns.
        '''
        self.axes.plot(dat[cols[0]],dat[cols[1]],',')
        if lbl :
            self.axes.set_xlabel(lbl[cols[0]])
            self.axes.set_ylabel(lbl[cols[1]])

    def add_toolbar(self):
        self.toolbar = NavigationToolbar2Wx(self.canvas)
        self.toolbar.Realize()
        if wx.Platform == '__WXMAC__':
            # Mac platform (OSX 10.3, MacPython) does not seem to cope with
            # having a toolbar in a sizer. This work-around gets the buttons
            # back, but at the expense of having the toolbar at the top
            self.SetToolBar(self.toolbar)
        else:
            # On Windows platform, default window size is incorrect, so set
            # toolbar width to figure width.
            tw, th = self.toolbar.GetSizeTuple()
            fw, fh = self.canvas.GetSizeTuple()
            # By adding toolbar in sizer, we are able to put it at the bottom
            # of the frame - so appearance is closer to GTK version.
            # As noted above, doesn't work for Mac.
            self.toolbar.SetSize(wx.Size(fw, th))
            self.sizer.Add(self.toolbar, 0, wx.LEFT | wx.EXPAND)
        # update the axes menu on the toolbar
        self.toolbar.update()


    def OnPaint(self, event):
        self.canvas.draw()




class App(wx.App):

    def OnInit(self):
        'Create the main window and insert the custom frame'
        frame = CanvasFrame()
        frame.Show(True)

        return True


if __name__ == '__main__':


    app = App(0)
    app.MainLoop()

