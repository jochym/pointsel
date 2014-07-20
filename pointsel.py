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
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg as NavToolbar
from matplotlib.backends.backend_wx import _load_bitmap, bind, StatusBarWx

from matplotlib.figure import Figure
from matplotlib.widgets import RectangleSelector
from matplotlib.patches import Rectangle

import wx
import matplotlib as mpl
import matplotlib.pyplot as plt

class RectSelector(RectangleSelector):
    '''
    Works only in data coordinates!
    '''
    def __init__(self, ax, onselect, button=None,
                 minspanx=None, minspany=None, useblit=True,
                 lineprops=None, rectprops=dict(facecolor='red', edgecolor = 'black',
                           alpha=0.5, fill=True), proxy=5):
        RectangleSelector.__init__(self, ax=ax, onselect=onselect, 
                        drawtype='box', spancoords='data',
                        minspanx=minspanx, minspany=minspany, 
                        useblit=useblit, 
                        lineprops=lineprops, rectprops=rectprops, 
                        button=button)
        self.mod=False
        self.fixedSize=None
        self.prevEvents=None
        self.proxy=proxy
        print('Init')

    def close_to_handles(self, ev):
        return True
    
    def opposite_corner(self, ev):
        return ev.xdata, ev.ydata
    
    def setSize(self, w=None, h=None):
        if w is not None and h is not None:
            self.fixedSize=(w,h)
            if self.prevEvents :
                pe, re=self.prevEvents
                cx=(pe.xdata+re.xdata)/2
                cy=(pe.ydata+re.ydata)/2
                dw=w/2
                dh=h/2
                pe.xdata = cx-dw
                re.xdata = cx+dw
                pe.ydata = cy-dh
                re.ydata = cy+dh
                self.wdata=(pe.xdata-re.xdata)/2
                self.hdata=(pe.ydata-re.ydata)/2
        else :
            self.fixedSize=None

    def press(self, ev):
        if self.ignore(ev):
            return
        if not self.fixedSize :
            # Free selection box
            if self.prevEvents :
                # Some ROI is selected. 
                # Modify it if we are close to one corner.
                pass
            else :
                # We are first time here. Just select.
                pass
        else:
            # The size is fixed. The box should be panned.
            if self.prevEvents :
                # Some ROI is selected. We need to move it.
                # Move the centre of the roi to the press point.
                ev.xdata+=self.wdata
                ev.ydata+=self.hdata
                RectangleSelector.press(self,ev)
            else :
                # We are first time here. Build up the roi.
                pass
        RectangleSelector.press(self,ev)
            
        
    def release(self, ev):
        if self.eventpress is None or self.ignore(ev):
            return
        if not self.fixedSize :
            # Free selection, just do the normal thing
            pass
        elif self.prevEvents :
            # Panning mode. Modify the existing ROI. Do the shift.
            ev.xdata+=self.wdata
            ev.ydata+=self.hdata
        else :
            # Panning mode but first time here.
            pass
        self.prevEvents=(self.eventpress,ev)
        pe, re=self.prevEvents
        self.wdata=(pe.xdata-re.xdata)/2
        self.hdata=(pe.ydata-re.ydata)/2
        RectangleSelector.release(self, ev)

    def onmove(self, ev):
        if self.eventpress is None or self.ignore(ev):
            return
        if not self.fixedSize :
            # Free selection, just do the normal thing
            pass
        elif self.prevEvents :
            # Panning mode. Modify the existing ROI. Do the shift.
            ev.xdata+=self.wdata
            ev.ydata+=self.hdata
            self.eventpress.xdata=ev.xdata-2*self.wdata
            self.eventpress.ydata=ev.ydata-2*self.hdata
        else :
            # Panning mode but first time here.
            pass
        RectangleSelector.onmove(self, ev)
            

class CustomToolbar(NavToolbar): 
    
    toolitems=NavToolbar.toolitems + (
        (None, None, None, None),
        ('ROI', 'Select ROI', 'selection', '_on_custom_select'),
    )

    def __init__(self, plotCanvas):
        # create the default toolbar
        NavToolbar.__init__(self, plotCanvas)
        self.selector = RectSelector(self.canvas.figure.axes[0], 
                            self.onSelect, button=[1,3], # don't use middle button
                             minspanx=5, minspany=5)
        self.selector.set_active(False)
        self.roi=None
        self.fixedSize=False

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

    def _update_view(self):
        NavToolbar._update_view(self)
        # MacOS needs a forced draw to update plot
        if wx.Platform == '__WXMAC__':
            self.canvas.draw()

    def draw(self):
        NavToolbar.draw(self)
        # MacOS needs a forced draw to update plot
        if wx.Platform == '__WXMAC__':
            self.canvas.draw()

    def draw_rubberband(self, event, x0, y0, x1, y1):
        # XOR does not work on MacOS ...
        if wx.Platform != '__WXMAC__':
            NavToolbar.draw_rubberband(self, event, x0, y0, x1, y1)
        else :
            print('MAC...')
            'adapted from http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/189744'
            canvas = self.canvas
            dc =wx.ClientDC(canvas)

            # Set logical function to XOR for rubberbanding
            dc.SetLogicalFunction(wx.XOR)

            # Set dc brush and pen
            # Here I set brush and pen to white and grey respectively
            # You can set it to your own choices

            # The brush setting is not really needed since we
            # dont do any filling of the dc. It is set just for
            # the sake of completion.

            wbrush =wx.Brush(wx.Colour(255,255,255), wx.TRANSPARENT)
            wpen =wx.Pen(wx.Colour(200, 200,200), 1, wx.SOLID)
            dc.SetBrush(wbrush)
            dc.SetPen(wpen)


            dc.ResetBoundingBox()
            dc.BeginDrawing()
            height = self.canvas.figure.bbox.height
            y1 = height - y1
            y0 = height - y0

            if y1<y0: y0, y1 = y1, y0
            if x1<y0: x0, x1 = x1, x0

            w = x1 - x0
            h = y1 - y0

            rect = int(x0), int(y0), int(w), int(h)
                
            try: 
                lastrect = self.lastrect
            except AttributeError: 
                # Copy the picture into buffer
                print('blit out')
                self.background = self.canvas.copy_from_bbox(self.canvas.figure.bbox)
            else: 
                #erase last
                print('blit in')
                self.canvas.restore_region(self.background)
            self.lastrect = rect
            dc.DrawRectangle(*rect)
            dc.EndDrawing()


    # Turn on selection
    # TODO: Proper handling of states, actual functionality.
    def _on_custom_select(self, evt):
        for id in ['Zoom','Pan']:
            self.ToggleTool(self.wx_ids[id], False)

        print('Select ROI: %s' % (self.GetToolState(self.wx_ids['ROI'])))
        self.ToggleTool(self.wx_ids['ROI'], 
                self.GetToolState(self.wx_ids['ROI']) )
        self.toggle_selector()
        print('Select ROI: %s' % (self.GetToolState(self.wx_ids['ROI'])))
        

    def onSelect(self, eclick, erelease):
        'eclick and erelease are matplotlib events at press and release'
        print(' startposition : (%f, %f)' % (eclick.xdata, eclick.ydata))
        print(' endposition   : (%f, %f)' % (erelease.xdata, erelease.ydata))
        print(' used button   : ', eclick.button)
        if self.roi :
            self.roi.set_bounds(min(eclick.xdata,erelease.xdata),
                                min(eclick.ydata,erelease.ydata),
                                abs(eclick.xdata-erelease.xdata),
                                abs(eclick.ydata-erelease.ydata))
        else :
            self.roi=Rectangle((min(eclick.xdata,erelease.xdata),
                                min(eclick.ydata,erelease.ydata)),
                                abs(eclick.xdata-erelease.xdata),
                                abs(eclick.ydata-erelease.ydata),
                                ls='solid', lw=2, color='r', fill=False, 
                                zorder=5)
            self.canvas.figure.axes[0].add_patch(self.roi)
        self.updateCanvas()
        print(self.roi.get_bbox())
        

    def toggle_selector(self):
        self.selector.set_active(not self.selector.active)

    def onFixedSize(self, ev):
        self.fixedSize=ev.IsChecked()
        self.updateCanvas()
        
    def onWidthChange(self, ev):
        x=self.roi.get_x()
        w=self.roi.get_width()
        nw=ev.GetValue()
        self.roi.set_x(x+(w-nw)/2)
        self.roi.set_width(nw)
        self.updateCanvas()

    def onHeightChange(self, ev):
        y=self.roi.get_y()
        h=self.roi.get_height()
        nh=ev.GetValue()
        self.roi.set_y(y+(h-nh)/2)
        self.roi.set_height(nh)
        self.updateCanvas()
        
    def updateCanvas(self, redraw=True):
        self.canvas.parentFrame.setWH(self.roi.get_width(),self.roi.get_height())
        if self.fixedSize :
            self.selector.setSize(self.roi.get_width(),self.roi.get_height())
        else :
            self.selector.setSize()
        if redraw : self.draw()


class StatusBar(wx.StatusBar):
    """
    A status bar is added to _FigureFrame to allow measurements and the
    previously selected scroll function to be displayed as a user
    convenience.
    """
    def __init__(self, parent):
        wx.StatusBar.__init__(self, parent, -1)
        self.SetFieldsCount(3)
        self.SetStatusText("None", 1)
        self.SetStatusText("Area: None", 2)
        #self.Reposition()

    def set_function(self, string):
        self.SetStatusText("%s" % string, 1)

    def set_measurement(self, a):
        self.SetStatusText("Area: %.2f um^2" % a, 2)


class CanvasFrame(wx.Frame):

    def __init__(self):
        wx.Frame.__init__(self,None,-1,
                            'Point Selector', size=(800,600))

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
        self.Bind(wx.EVT_MENU, self.onOpen, menuOpen)
        self.Bind(wx.EVT_MENU, self.onSave, menuSave)
        self.Bind(wx.EVT_MENU, self.onExit, menuExit)
        self.Bind(wx.EVT_MENU, self.onAbout, menuAbout)

        self.figure = Figure()
        self.axes = self.figure.add_subplot(111)

        
        self.datfn=''
        self.dat=[['',''],array([[],[]])]
        self.dirname, self.filename= os.path.split(self.datfn)

        self.plot,=self.axes.plot([],[],',')
        self.displayData(self.dat[1],self.dat[0])

        self.statbar = StatusBar(self)
        self.SetStatusBar(self.statbar)
        self.canvas = FigureCanvas(self, -1, self.figure)
        self.canvas.parentFrame=self
        self.canvas.SetInitialSize(wx.Size(self.figure.bbox.width, 
                                            self.figure.bbox.height))
        self.canvas.SetFocus()

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Build the parameters bar
        self.parbarSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.fixedSizeCB = wx.CheckBox(self, style=wx.ALIGN_RIGHT)
        self.parbarSizer.Add(wx.StaticText(self,label='Fixed size', style=wx.ALIGN_RIGHT), 0, wx.CENTER)
        self.parbarSizer.Add(self.fixedSizeCB,0, wx.CENTER | wx.LEFT)
        self.widthCtrl = wx.SpinCtrlDouble(self, min=0, initial=0, inc=0.1)
        self.heightCtrl = wx.SpinCtrlDouble(self, min=0, initial=0, inc=0.1)
        self.parbarSizer.Add(wx.StaticText(self,label='  W x H: ', style=wx.ALIGN_RIGHT), 0, wx.CENTER)
        self.parbarSizer.Add(self.widthCtrl, 0, wx.TOP | wx.LEFT)
        self.parbarSizer.Add(wx.StaticText(self,label=' x ', style=wx.ALIGN_RIGHT), 0, wx.CENTER)
        self.parbarSizer.Add(self.heightCtrl, 0, wx.TOP | wx.LEFT)
        self.parbarSizer.Add(wx.StaticText(self,label=' um^2', style=wx.ALIGN_RIGHT), 0, wx.CENTER)
        self.sizer.Add(self.parbarSizer, 0, wx.TOP | wx.LEFT)
        
        # Add plot canvas
        self.sizer.Add(self.canvas, 1, wx.TOP | wx.LEFT | wx.EXPAND)

        # Add toolbar
        self.toolbar=self._get_toolbar(self.statbar)
        
        # Bind the methods to the GUI elements
        self.fixedSizeCB.Bind(wx.EVT_CHECKBOX, self.toolbar.onFixedSize)
        self.widthCtrl.Bind(wx.EVT_SPINCTRLDOUBLE, self.onWidthChange)
        self.heightCtrl.Bind(wx.EVT_SPINCTRLDOUBLE, self.onHeightChange)
                
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

        # Read example data. To be removed in the future.
        try :
            self.datfn=sys.argv[1]
        except IndexError :
            # Example data
            self.datfn='data/A339-SiC-560-1-SiC-WDS.txt'

        try :
            self.dirname, self.filename=os.path.split(self.datfn)
            self.dat=self.readData(self.datfn)
            self.displayData(self.dat[1],self.dat[0])
            self.axes.set_title(self.filename)
        except IOError :
            print('Warning: Cannot open file ', self.datfn)

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
        r = [lbl, array([
                        map(float,
                            ln.replace(';',' ').replace(',','.').split()) 
                        for ln in df[skip:]]).T]
        d=r[1][:2]
        self.minX=min(d[0])
        self.minY=min(d[1])
        self.maxX=max(d[0])
        self.maxY=max(d[1])
        self.setLimits()
        return r

    def setLimits(self):
        self.widthCtrl.SetMax(self.maxX-self.minX)
        self.heightCtrl.SetMax(self.maxY-self.minY)
        
    def setWH(self, w, h):
        self.widthCtrl.SetValue(w)
        self.heightCtrl.SetValue(h)
        self.statbar.set_measurement(w*h)

    def displayData(self, dat, lbl=None, cols=(0,1)):
        '''
        Display the points in the cols of the dat array.
        The axes are lebeled with labels from the lbl parameter.
        The lbl must contain a list of labels for columns.
        '''
        self.axes.set_autoscale_on(True)
        #self.plot.set_data([],[])
        self.plot.set_data(dat[cols[0]],dat[cols[1]])
        self.axes.set_title(self.filename)
        if lbl :
            self.axes.set_xlabel(lbl[cols[0]])
            self.axes.set_ylabel(lbl[cols[1]])
        #self.axes.legend((self.filename,))

    def redrawPlot(self):
        self.axes.relim()
        self.axes.autoscale_view(True,True,True)
        self.figure.canvas.draw()


    def onAbout(self,e):
        # Create a message dialog box
        dlg = wx.MessageDialog(self, "A data point selector", "About PointSel", wx.OK)
        dlg.ShowModal() # Shows it
        dlg.Destroy() # finally destroy it when finished.

    def onExit(self,e):
        self.Close(True)  # Close the frame.

    def onOpen(self,e):
        """ Open a file"""
        dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "*.*", wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.filename = dlg.GetFilename()
            self.dirname = dlg.GetDirectory()
            self.datfn=os.path.join(self.dirname, self.filename)
            self.dat=self.readData(self.datfn)
            self.displayData(self.dat[1],self.dat[0])
            self.redrawPlot()
        dlg.Destroy()

    def onPaint(self, event):
        self.canvas.draw()

    def onSave(self, e):
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

    def onFixedSize(self, ev):
        print('Fixed:',ev.IsChecked())
        if self.toolbar :
            slef.toolbar.onFixedSize(ev)
        
    def onWidthChange(self, ev):
        print('Width:',ev.GetValue())
        if self.toolbar :
            self.toolbar.onWidthChange(ev)

    def onHeightChange(self, ev):
        print('Height:',ev.GetValue())
        if self.toolbar :
            self.toolbar.onHeightChange(ev)



class App(wx.App):

    def OnInit(self):
        'Create the main window and insert the custom frame'
        frame = CanvasFrame()
        frame.Show(True)

        return True


if __name__ == '__main__':


    app = App(False)
    app.MainLoop()

