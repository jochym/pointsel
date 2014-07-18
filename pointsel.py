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
import sys, os
import matplotlib
import wxversion
wxversion.ensureMinimal('2.8')
matplotlib.use('WXAgg')

from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wx import _load_bitmap, bind
from matplotlib.backends.backend_wx import NavigationToolbar2Wx, StatusBarWx

from matplotlib.figure import Figure

import wx
import matplotlib as mpl
import matplotlib.pyplot as plt


class CustomToolbar(NavigationToolbar2Wx): 
    
    toolitems=NavigationToolbar2Wx.toolitems + (
        (None, None, None, None),
        ('ROI', 'Select ROI', 'selection', '_on_custom_select'),
    )

    def __init__(self, plotCanvas):
        # create the default toolbar
        NavigationToolbar2Wx.__init__(self, plotCanvas)

    def _init_toolbar(self):
        self._parent = self.canvas.GetParent()

        self.wx_ids = {}
        for text, tooltip_text, image_file, callback in self.toolitems:
            if text is None:
                self.AddSeparator()
                continue
            self.wx_ids[text] = wx.NewId()
            try :
                bitmap=_load_bitmap(image_file + '.png')
            except IOError :
                bitmap=wx.Bitmap(image_file + '.png')
            if text in ['Pan', 'Zoom', 'ROI']:
               self.AddCheckTool(self.wx_ids[text], bitmap,
                                 shortHelp=text, longHelp=tooltip_text)
            else:
               self.AddSimpleTool(self.wx_ids[text], bitmap,
                                  text, tooltip_text)
            bind(self, wx.EVT_TOOL, getattr(self, callback), id=self.wx_ids[text])

        self.Realize()


    # Turn on selection
    def _on_custom_select(self, evt):
        for id in ['Zoom','Pan']:
            self.ToggleTool(self.wx_ids[id], False)

        print('Select ROI: %s' % (self.GetToolState(self.wx_ids['ROI'])))
        self.ToggleTool(self.wx_ids['ROI'], 
                self.GetToolState(self.wx_ids['ROI']) )
        print('Select ROI: %s' % (self.GetToolState(self.wx_ids['ROI'])))


class CanvasFrame(wx.Frame):

    def __init__(self):
        wx.Frame.__init__(self,None,-1,
                            'CanvasFrame', size=(800,600))

        self.dirname=''
        self.filename=''
        self.SetBackgroundColour(wx.NamedColour("WHITE"))

        # Setting up the menu.
        filemenu= wx.Menu()
        menuOpen = filemenu.Append(wx.ID_OPEN, 
                    "&Open"," Open a data file")
        menuSave = filemenu.Append(wx.ID_SAVE, 
                    "&Save"," Open a file to save the selected data")
        menuAbout= filemenu.Append(wx.ID_ABOUT, 
                    "&About"," Information about this program")
        menuExit = filemenu.Append(wx.ID_EXIT,
                    "E&xit"," Terminate the program")

        # Creating the menubar.
        menuBar = wx.MenuBar()
        menuBar.Append(filemenu,"&File") 

        # Adding the "filemenu" to the MenuBar
        self.SetMenuBar(menuBar)  # Adding the MenuBar to the Frame content.

        # Events.
        self.Bind(wx.EVT_MENU, self.OnOpen, menuOpen)
        self.Bind(wx.EVT_MENU, self.OnSave, menuSave)
        self.Bind(wx.EVT_MENU, self.OnExit, menuExit)
        self.Bind(wx.EVT_MENU, self.OnAbout, menuAbout)

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
        
        self.dirname, self.filename= os.path.split(self.datfn)

        self.plot,=self.axes.plot([],[],',')
        self.axes.set_title('File: %s' % self.datfn)
        self.displayData(self.dat[1],self.dat[0])

        statbar = StatusBarWx(self)
        self.SetStatusBar(statbar)
        self.canvas = FigureCanvas(self, -1, self.figure)
        self.canvas.SetInitialSize(wx.Size(self.figure.bbox.width, 
                                            self.figure.bbox.height))
        self.canvas.SetFocus()

        self.sizer = wx.BoxSizer(wx.VERTICAL)
#        self.sizer.Add(self.canvas, 1, wx.LEFT | wx.TOP | wx.GROW)
        self.sizer.Add(self.canvas, 1, wx.TOP | wx.LEFT | wx.EXPAND)

        self.toolbar=self._get_toolbar(statbar)

        if self.toolbar is not None:
            self.toolbar.Realize()
            # Default window size is incorrect, so set
            # toolbar width to figure width.
            tw, th = self.toolbar.GetSizeTuple()
            fw, fh = self.canvas.GetSizeTuple()
            # By adding toolbar in sizer, we are able to put it at the bottom
            # of the frame - so appearance is closer to GTK version.
            self.toolbar.SetSize(wx.Size(fw, th))
            self.sizer.Add(self.toolbar, 0, wx.LEFT | wx.EXPAND)
            # update the axes menu on the toolbar
            self.toolbar.update()

        self.SetSizer(self.sizer)
        self.Fit()
        self.redrawPlot()


    def _get_toolbar(self, statbar):
        toolbar = CustomToolbar(self.canvas)
        #toolbar = NavigationToolbar2Wx(self.canvas)
        toolbar.set_status_bar(statbar)
        return toolbar

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
        self.axes.set_autoscale_on(True)
        #self.plot.set_data([],[])
        self.plot.set_data(dat[cols[0]],dat[cols[1]])
        #self.plot.set_label(self.filename)
        if lbl :
            self.axes.set_xlabel(lbl[cols[0]])
            self.axes.set_ylabel(lbl[cols[1]])
        #self.axes.legend((self.filename,))

    def redrawPlot(self):
        self.axes.relim()
        self.axes.autoscale_view(True,True,True)
        self.figure.canvas.draw()


    def OnAbout(self,e):
        # Create a message dialog box
        dlg = wx.MessageDialog(self, "A data point selector", "About PointSel", wx.OK)
        dlg.ShowModal() # Shows it
        dlg.Destroy() # finally destroy it when finished.

    def OnExit(self,e):
        self.Close(True)  # Close the frame.

    def OnOpen(self,e):
        """ Open a file"""
        dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "*.*", wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.filename = dlg.GetFilename()
            self.dirname = dlg.GetDirectory()
            self.datfn=os.path.join(self.dirname, self.filename)
            self.dat=self.readData(self.datfn)
            self.displayData(self.dat[1],self.dat[0])
            self.axes.set_title(self.filename)
            self.redrawPlot()
        dlg.Destroy()

    def OnPaint(self, event):
        self.canvas.draw()

    def OnSave(self, e):
        '''Save the selected points'''
        dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "*.*", wx.SAVE)
        if dlg.ShowModal() == wx.ID_OK:
            # The file name is local here.
            # We are saving a selection not the data.
            filename = dlg.GetFilename()
            dirname = dlg.GetDirectory()
            datfn=os.path.join(dirname, filename)
            print('Will save into', datfn)
        dlg.Destroy()


class App(wx.App):

    def OnInit(self):
        'Create the main window and insert the custom frame'
        frame = CanvasFrame()
        frame.Show(True)

        return True


if __name__ == '__main__':


    app = App(False)
    app.MainLoop()

