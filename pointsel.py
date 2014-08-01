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
from scipy.optimize import bisect
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

from matplotlib import rcParams

import wx
import matplotlib as mpl
import matplotlib.pyplot as plt

rcParams['savefig.format']='tif'

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
                        
        self.fixedSize=None
        self.prevEvents=None
        self.proxy=max(self.ax.transData.transform_point((proxy/100, proxy/100))-
                    self.ax.transData.transform_point((0, 0)))

    def close_to_handles(self, ev):
        '''
            Return zero or number of the closest corner.
            2 3
            1 4
        '''
        if not self.prevEvents :
            return False
        x,y=ev.xdata, ev.ydata
        pe, re=self.prevEvents
        l, r=min(pe.xdata,re.xdata), max(pe.xdata,re.xdata)
        b, t=min(pe.ydata,re.ydata), max(pe.ydata,re.ydata)
        d=self.proxy
        if ( abs(l-x)<d or abs(r-x)<d ) and (abs(b-y)<d or abs(t-y)<d) :
            #print('LTRB:', l,t,r,b, x, y)
            if abs(l-x)<d :
                if abs(b-y)<d : return 1
                else : return 2
            else :
                if abs(t-y)<d : return 3
                else : return 4
        else :
            return 0
    
    def getLTRB(self):
        pe, re=self.prevEvents
        l, r=min(pe.xdata,re.xdata), max(pe.xdata,re.xdata)
        b, t=min(pe.ydata,re.ydata), max(pe.ydata,re.ydata)
        return l, t, r, b

    def opposite_corner(self, pos):
        l,t,r,b=self.getLTRB()
        cl=[[r,t],[r,b],[l,b],[l,t]]
        return cl[pos-1]
        
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
        h=self.close_to_handles(ev)
        if not self.fixedSize and self.prevEvents and h :
            # Not fixed size and active roi. 
            # Clicked on the corner -> modify mode
            x,y=self.opposite_corner(h)
            self.to_draw.set_visible(self.visible)
            self.eventpress = ev
            self.eventpress.xdata=x
            self.eventpress.ydata=y
            return False
        else :
            RectangleSelector.press(self,ev)

        
    def release(self, ev):
        if self.eventpress is None or self.ignore(ev):
            return
        if self.fixedSize and self.prevEvents:
            # Panning mode. Modify the existing ROI. Do the shift.
            ev.xdata+=self.wdata
            ev.ydata+=self.hdata
            self.eventpress.xdata=ev.xdata-2*self.wdata
            self.eventpress.ydata=ev.ydata-2*self.hdata

        self.prevEvents=(self.eventpress,ev)
        pe, re=self.prevEvents
        self.wdata=(pe.xdata-re.xdata)/2
        self.hdata=(pe.ydata-re.ydata)/2
        RectangleSelector.release(self, ev)

    def onmove(self, ev):
        if self.eventpress is None or self.ignore(ev):
            return
        if self.fixedSize and self.prevEvents :
            # Panning mode. Modify the existing ROI. Do the shift.
            ev.xdata+=self.wdata
            ev.ydata+=self.hdata
            self.eventpress.xdata=ev.xdata-2*self.wdata
            self.eventpress.ydata=ev.ydata-2*self.hdata
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
        self.ax=self.canvas.figure.axes[0]
        self.roi=None
        self.fixedSize=False
        if wx.Platform == '__WXMAC__' :
            self.to_draw = Rectangle((0, 0), 0, 1, visible=False, 
                                facecolor='yellow', edgecolor = 'black',
                                alpha=0.5, fill=True)
            self.ax.add_patch(self.to_draw)
            self.background=None

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

    def _set_markers(self):
        self.canvas.parentFrame.set_markers()

    def _update_view(self):
        NavToolbar._update_view(self)
        self._set_markers()
        # MacOS needs a forced draw to update plot
        if wx.Platform == '__WXMAC__':
            self.canvas.draw()

    def draw(self):
        self._set_markers()
        NavToolbar.draw(self)
        # MacOS needs a forced draw to update plot
        if wx.Platform == '__WXMAC__':
            self.canvas.draw()

    def zoom(self, ev):
        if wx.Platform == '__WXMAC__' :
            self.ToggleTool(self.wx_ids['Zoom'], self.GetToolState(self.wx_ids['Zoom']))
        NavToolbar.zoom(self,ev)

    def pan(self, ev):
        if wx.Platform == '__WXMAC__' :
            self.ToggleTool(self.wx_ids['Pan'], self.GetToolState(self.wx_ids['Pan']))
        NavToolbar.pan(self,ev)

    def press_zoom(self, ev):
        if wx.Platform == '__WXMAC__':
            self.update_background()
            self.to_draw.set_visible(True)
        NavToolbar.press_zoom(self,ev)

    def release_zoom(self, ev):
        if wx.Platform == '__WXMAC__':
            self.to_draw.set_visible(False)
        NavToolbar.release_zoom(self,ev)

    def draw_rubberband(self, event, x0, y0, x1, y1):
        # XOR does not work on MacOS ...
        if wx.Platform != '__WXMAC__':
            NavToolbar.draw_rubberband(self, event, x0, y0, x1, y1)
        else :
            if self.background is not None:
                self.canvas.restore_region(self.background)
            c0, c1=self.ax.transData.inverted().transform([[x0,y0],[x1,y1]])
            l,b=c0
            r,t=c1
            self.to_draw.set_bounds(l,b,r-l,t-b)
            self.ax.draw_artist(self.to_draw)
            self.canvas.blit(self.ax.bbox)

    def update_background(self):
        """force an update of the background"""
        self.background = self.canvas.copy_from_bbox(self.ax.bbox)

    # Turn on selection
    # TODO: Proper handling of states, actual functionality.
    def _on_custom_select(self, evt):
#        for id in ['Zoom','Pan']:
#            self.ToggleTool(self.wx_ids[id], False)
#        print('Select ROI: %s' % (self.GetToolState(self.wx_ids['ROI'])))
#        self.ToggleTool(self.wx_ids['ROI'], 
#                self.GetToolState(self.wx_ids['ROI']) )
        self.toggle_selector()
#        print('Select ROI: %s' % (self.GetToolState(self.wx_ids['ROI'])))

    def onSelect(self, eclick, erelease):
        'eclick and erelease are matplotlib events at press and release'
#        print(' startposition : (%f, %f)' % (eclick.xdata, eclick.ydata))
#        print(' endposition   : (%f, %f)' % (erelease.xdata, erelease.ydata))
#        print(' used button   : ', eclick.button)
        self.updateROI(min(eclick.xdata,erelease.xdata),
                       min(eclick.ydata,erelease.ydata),
                       abs(eclick.xdata-erelease.xdata),
                       abs(eclick.ydata-erelease.ydata))
        if self.canvas.parentFrame.fixedNumberCB.IsChecked() :
            # We are working in the fixed-number mode
            # We need to find new roi for this center point
            # The handler will call the update ROI function for us.
            self.canvas.parentFrame.handleROIforN()

    def updateROI(self, x, y, w, h):
        if self.roi is None :
            #print('upd ROI:', x, y, w, h)
            self.roi=Rectangle((x,y),w,h,
                                ls='solid', lw=2, color='r', fill=False, 
                                zorder=5)
            self.canvas.figure.axes[0].add_patch(self.roi)
        else :
            self.roi.set_bounds(x,y,w,h)
        self.updateCanvas()

    def toggle_selector(self):
        self.selector.set_active(not self.selector.active)

    def onFixedSize(self, ev):
        self.fixedSize=ev.IsChecked()
        self.updateCanvas()
        
    def onWidthChange(self, ev):
        if self.roi :
            x=self.roi.get_x()
            w=self.roi.get_width()
            nw=ev.GetValue()
            self.roi.set_x(x+(w-nw)/2)
            self.roi.set_width(nw)
            self.updateCanvas()

    def onHeightChange(self, ev):
        if self.roi :
            y=self.roi.get_y()
            h=self.roi.get_height()
            nh=ev.GetValue()
            self.roi.set_y(y+(h-nh)/2)
            self.roi.set_height(nh)
            self.updateCanvas()
        
    def updateCanvas(self, redraw=True):
        if self.roi :
            self.canvas.parentFrame.showROI(self.roi.get_x(),
                                            self.roi.get_y(),
                                            self.roi.get_width(),
                                            self.roi.get_height())
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
        self.SetFieldsCount(2)
        self.SetStatusText("None", 1)
        #self.Reposition()

    def set_function(self, string):
        self.SetStatusText("%s" % string, 1)


class CanvasFrame(wx.Frame):

    def __init__(self):
        wx.Frame.__init__(self,None,-1,
                            'Point Selector')

        self.dirname=''
        self.filename=''
        self.SetBackgroundColour(wx.NamedColour("WHITE"))
        self.SetFont(wx.Font(18 if wx.Platform == '__WXMAC__' else 11, 
                                wx.FONTFAMILY_TELETYPE, wx.NORMAL, wx.NORMAL))


        # Setting up the menu.
        filemenu= wx.Menu()
        menuOpen = filemenu.Append(wx.ID_OPEN, 
                    "&Open"," Open a data file")
        menuExport = filemenu.Append(wx.ID_SAVE, 
                    "&Export selection"," Export selected data to a file.")
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
        self.Bind(wx.EVT_MENU, self.onExport, menuExport)
        self.Bind(wx.EVT_MENU, self.onExit, menuExit)
        self.Bind(wx.EVT_MENU, self.onAbout, menuAbout)

        self.numSelected = 0
        self.targetSelected = 0
        self.numPoints = 0
        self.figure = Figure(figsize=(10,10))
        self.figure.set_tight_layout(True)
        self.axes = self.figure.add_subplot(111)

        
        self.datfn=''
        self.dat=[['',''],array([[],[]])]
        self.dirname, self.filename= os.path.split(self.datfn)

        self.plot,=self.axes.plot([],[],',')
        self.axes.grid(color='k', alpha=0.75, lw=1, ls='-')
        
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
        self.fixedSizeCB = wx.CheckBox(self, label='Fixed size', style=wx.ALIGN_RIGHT)
        self.parbarSizer.Add(self.fixedSizeCB,0, wx.CENTER | wx.LEFT)
        self.widthCtrl = wx.SpinCtrlDouble(self, min=0, initial=0, inc=1)
        self.heightCtrl = wx.SpinCtrlDouble(self, min=0, initial=0, inc=1)
        self.widthCtrl.SetDigits(2)
        self.heightCtrl.SetDigits(2)
        self.titleCtrl = wx.TextCtrl(self, value='', size=(200,-1))
        self.parbarSizer.Add(wx.StaticText(self,label='  W: ', style=wx.ALIGN_RIGHT), 0, wx.CENTER)
        self.parbarSizer.Add(self.widthCtrl, 0, wx.TOP | wx.LEFT)
        self.parbarSizer.Add(wx.StaticText(self,label='um   H: ', style=wx.ALIGN_RIGHT), 0, wx.CENTER)
        self.parbarSizer.Add(self.heightCtrl, 0, wx.TOP | wx.LEFT)
        self.parbarSizer.Add(wx.StaticText(self,label=' um', style=wx.ALIGN_RIGHT), 0, wx.CENTER)
        self.parbarSizer.Add(wx.StaticText(self,label='  #Points', style=wx.ALIGN_RIGHT), 0, wx.CENTER)
        self.fixedNumberCB = wx.CheckBox(self, style=wx.ALIGN_LEFT)
        self.parbarSizer.Add(self.fixedNumberCB,0, wx.CENTER | wx.LEFT)
        self.numPtsCtrl = wx.SpinCtrl(self, min=0, max=1000, initial=0)
        self.numPtsCtrl.Disable()
        self.parbarSizer.Add(self.numPtsCtrl, 0, wx.TOP | wx.LEFT)
        self.parbarSizer.Add(wx.StaticText(self,label='  Title:', style=wx.ALIGN_RIGHT), 0, wx.CENTER)
        self.parbarSizer.Add(self.titleCtrl, 0, wx.TOP | wx.LEFT)
        
        # Build the side bar
        self.sideBar = wx.BoxSizer(wx.VERTICAL)
        heading = wx.StaticText(self, label='Measurements', )
        heading.SetFont(self.GetFont().MakeBold())
        self.sideBar.Add(heading, 0, wx.TOP | wx.ALIGN_CENTER) 
        self.sideBar.Add(wx.StaticLine(self,size=(100,-1)), 0, wx.BOTTOM | wx.CENTER)
        self.sideBar.AddSpacer(3)
        self.positionDSP = wx.StaticText(self, style=wx.ALIGN_LEFT)
        self.sideBar.Add(self.positionDSP, 0, wx.BOTTOM | wx.LEFT)
        self.sideBar.AddSpacer(3)
        self.whDSP = wx.StaticText(self, style=wx.ALIGN_LEFT)
        self.sideBar.Add(self.whDSP, 0, wx.BOTTOM | wx.LEFT)
        self.sideBar.AddSpacer(3)
        self.areaDSP = wx.StaticText(self, style=wx.ALIGN_LEFT)
        self.sideBar.Add(self.areaDSP, 0, wx.BOTTOM | wx.LEFT)
        self.sideBar.AddSpacer(3)
        self.numberDSP = wx.StaticText(self, style=wx.ALIGN_LEFT)
        self.sideBar.Add(self.numberDSP, 0, wx.BOTTOM | wx.LEFT)
        self.sideBar.AddSpacer(3)
        self.sideBar.Add(wx.StaticLine(self,size=(100,-1)), 0, wx.BOTTOM | wx.CENTER)
        
        # Anchor switch
        self.anchorRB = wx.RadioBox(self, label='Anchor', 
                                    choices=['LT','L','LB','T','C','B','RT','R','RB'],
                                    majorDimension=3,
                                    style= wx.RA_SPECIFY_ROWS)
        # Center is default
        self.anchorRB.SetSelection(4)
        self.sideBar.Add(self.anchorRB, 0, wx.BOTTOM | wx.LEFT)
        
        # Zoom buttons
        box = wx.BoxSizer(wx.HORIZONTAL)
        self.flipXBTN=wx.BitmapButton(self,bitmap=wx.Bitmap('flip_x.png'))
        self.flipYBTN=wx.BitmapButton(self,bitmap=wx.Bitmap('flip_y.png'))
        box.Add(self.flipXBTN, 0, wx.TOP | wx.LEFT)
        box.Add(self.flipYBTN, 0, wx.TOP | wx.LEFT)
        self.sideBar.Add(box, 0, wx.TOP | wx.CENTER)
        
        # Build the window
        self.sizer.Add(self.parbarSizer, 0, wx.TOP | wx.LEFT)
        
        # Add plot canvas and sidebar
        cont=wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(cont, 1, wx.TOP | wx.LEFT | wx.EXPAND)
        cont.Add(self.canvas, 1, wx.TOP | wx.LEFT | wx.EXPAND)
        cont.AddSpacer(3)
        cont.Add(self.sideBar, 0, wx.TOP | wx.RIGHT )
        cont.AddSpacer(3)

        # Add toolbar
        self.toolbar=self._get_toolbar(self.statbar)
        
        # Bind the methods to the GUI elements
        self.fixedSizeCB.Bind(wx.EVT_CHECKBOX, self.toolbar.onFixedSize)
        self.widthCtrl.Bind(wx.EVT_SPINCTRLDOUBLE, self.onWidthChange)
        self.heightCtrl.Bind(wx.EVT_SPINCTRLDOUBLE, self.onHeightChange)
        self.fixedNumberCB.Bind(wx.EVT_CHECKBOX, self.onFixedNumber)
        self.numPtsCtrl.Bind(wx.EVT_SPINCTRL, self.onNumberChange)
        self.titleCtrl.Bind(wx.EVT_TEXT, self.onTitleChange)
        self.anchorRB.Bind(wx.EVT_RADIOBOX, self.onAnchorChange)
        self.flipXBTN.Bind(wx.EVT_BUTTON, self.onFlipX)
        self.flipYBTN.Bind(wx.EVT_BUTTON, self.onFlipY)
        
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
        
        self.titleCtrl.SetValue(self.filename)
        self.redrawPlot()

        # Init sidebar
        self.showPos()
        self.showWH()
        self.showArea()
        self.showNumber()

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
            lbl=df[0].replace('#','').strip().split(';')
        else :
            lbl=None
        r = [lbl, array([
                        map(float,
                            ln.replace(';',' ').replace(',','.').split()) 
                        for ln in df[skip:] if ln[0]!='#']).T]
        d=r[1]
        #print(d.shape)
        self._shift_to_origin(d)
        return r

    def getSelected(self, lrbt=None):
        '''
        Return an array of points inside the lrbt bounding box.
        '''
        if lrbt is None :
            try :
                l,b,r,t=array(self.toolbar.roi.get_bbox()).reshape(4)
            except AttributeError :
                return None
        else :
            # The bbox is expected as l,r,b,t tuple!
            l,r,b,t=array(lrbt).reshape(4)
        #print('LTRB:', l,t,r,b)
        d=self.dat[1]
        sel=d[...,(l<d[0]) & (d[0]<r) & (b<d[1]) & (d[1]<t)]
        return sel

    def exportData(self, fn):
        hdr=' ;'.join([' %s' % s.strip() for s in self.dat[0]])
        sel=self.getSelected()
        if not sel is None :
            np.savetxt(fn, sel.T, fmt='%.3f', delimiter=' ', newline='\n', 
                            header=hdr, footer='', comments='#')
        else :
            wx.MessageBox('Nothing to save yet. Make some selection before trying to export data.',
                            'Nothing to export!')

    def setLimits(self):
        self.widthCtrl.SetMax(self.maxX-self.minX)
        self.heightCtrl.SetMax(self.maxY-self.minY)
        self.numPtsCtrl.SetRange(0,self.numPoints)
    
    def showArea(self, a=0):
        self.areaDSP.SetLabel('Area (um^2):  \n %-8g' % (a))
    
    def showPos(self, x=0, y=0):
        self.positionDSP.SetLabel(u'Position (um):  \n X: %-8g\n Y: %-8g' % (x, y))

    def showWH(self, w=0, h=0):
        self.whDSP.SetLabel('Size (um):  \n W: %-8g\n H: %-8g' % (w, h))

    def showNumber(self, n=0):
        self.numberDSP.SetLabel('Selected pnts: \n %-d' % (n))
    
    def showROI(self, x, y, w, h):
        self.showPos(x,y)
        self.showArea(w*h)
        self.showWH(w,h)

    def setWH(self, w, h):
        self.widthCtrl.SetValue(w)
        self.heightCtrl.SetValue(h)
        self.showArea(w*h)
        self.showWH(w,h)
        try :
            self.numSelected=self.getSelected().shape[1]
        except AttributeError :
            self.numSelected=0
        if not self.fixedNumberCB.IsChecked() :
            self.numPtsCtrl.SetValue(self.numSelected)
        self.showNumber(self.numSelected)

    def displayData(self, dat, lbl=None, cols=(0,1)):
        '''
        Display the points in the cols of the dat array.
        The axes are lebeled with labels from the lbl parameter.
        The lbl must contain a list of labels for columns.
        '''
        self.axes.set_autoscale_on(True)
        #self.plot.set_data([],[])
        self.plot.set_data(dat[cols[0]],dat[cols[1]])
        self.titleCtrl.SetValue(self.filename)
        if lbl :
            self.axes.set_xlabel(lbl[cols[0]])
            self.axes.set_ylabel(lbl[cols[1]])
        #self.axes.legend((self.filename,))

    def set_markers(self):
        sel=self.getSelected(self.axes.get_xlim()+self.axes.get_ylim())
        if sel.shape[1] < 5000 :
            self.plot.set_marker('o')
        else :
            self.plot.set_marker(',')


    def redrawPlot(self):
        self.axes.relim()
        self.axes.autoscale_view(True,True,True)
        self.set_markers()
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
            self.updateROI(0,0,self.maxX,self.maxY)
            self.axes.set_xlim(0,self.maxX)
            self.axes.set_ylim(0,self.maxY)
            self.toolbar._views.clear()
            self.toolbar._positions.clear()
            self.toolbar.push_current()
            self.redrawPlot()
        dlg.Destroy()

    def onPaint(self, event):
        self.canvas.draw()

    def onExport(self, e):
        '''Export the selected points'''
        dlg = wx.FileDialog(self, "Choose a file", self.dirname, "*.txt", 
                                "Data file (*.txt)|*.txt|"+
                                "Data file (*.dat)|*.dat|"+
                                "All files (*.*)|*.*", 
                                wx.SAVE|wx.FD_OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:
            # The file name is local here.
            # We are saving a selection not the data.
            filename = dlg.GetFilename()
            dirname = dlg.GetDirectory()
            self.exportData(os.path.join(dirname, filename))
        dlg.Destroy()

    def onFixedSize(self, ev):
        if self.toolbar :
            self.toolbar.onFixedSize(ev)
    
    def onFixedNumber(self, ev):
        if self.fixedNumberCB.IsChecked() :
            if self.toolbar.roi is None :
                wx.MessageBox('You need to make some selection before '+
                                'using fixed number of points selection mode.',
                                'Make a selection!')
                self.fixedNumberCB.SetValue(False)
                return
            self.numPtsCtrl.Enable()
            self.fixedSizeCB.SetValue(True)
            self.targetSelected=self.numPtsCtrl.GetValue()
            self.onFixedSize(ev)
            self.handleROIforN()
        else :
            self.numPtsCtrl.Disable()
            
    def updateROI(self, x, y, w, h):
        self.showArea(w*h)
        self.showPos(x,y)
        self.toolbar.updateROI(x,y,w,h)
        self.redrawPlot()
    
    def onWidthChange(self, ev):
        if self.toolbar :
            self.toolbar.onWidthChange(ev)

    def onHeightChange(self, ev):
        if self.toolbar :
            self.toolbar.onHeightChange(ev)

    def onNumberChange(self, ev):
        if not self.fixedNumberCB.IsChecked() :
            # Just reset the value to the number of selected points.
            self.numPtsCtrl.SetValue(self.numSelected)
            return
        self.targetSelected=self.numPtsCtrl.GetValue()
        self.handleROIforN()

    def onTitleChange(self, ev):
        self.axes.set_title(ev.GetString())
        self.redrawPlot()

    def onAnchorChange(self, ev):
        s=self.anchorRB.GetSelection()
        print(self.anchorRB.GetString(s))

    def _shift_to_origin(self, d=None):
        if d is None :
            d=self.dat[1]
        d[0]-=min(d[0])
        d[1]-=min(d[1])
        self.minX=0
        self.minY=0
        self.maxX=max(d[0])
        self.maxY=max(d[1])
        self.numPoints = d.shape[1]
        self.setLimits()

    def onFlipX(self, ev):
        self.dat[1][0]=-self.dat[1][0]
        self._shift_to_origin()
        self.plot.set_xdata(self.dat[1][0])
        self.toolbar.updateCanvas()

    def onFlipY(self, ev):
        self.dat[1][1]=-self.dat[1][1]
        self._shift_to_origin()
        self.plot.set_ydata(self.dat[1][1])
        self.toolbar.updateCanvas()

    def handleROIforN(self):
        '''
        GUI part of fixed number selection mode
        '''
        if not self.fixedNumberCB.IsChecked() :
            # Not our mode. Nothing to do!
            return
        n=self.targetSelected
        x,y=self.toolbar.roi.get_xy()
        w=self.toolbar.roi.get_width()
        h=self.toolbar.roi.get_height()
        cx, cy= x+w/2, y+h/2
        ncx, ncy, tw=self.findROIforN(cx,cy,n)
        #print('ROIforN:',cx,cy,tw)
        self.updateROI(ncx-tw/2,ncy-tw/2,tw,tw)
        self.setWH(tw,tw)

    def findROIforN(self, cx, cy, n):
        '''
        Find the squere ROI around target point (cx, cy) containing 
        as close as possible to target number of points (n). 
        The function does not care about the GUI. Just the computation.
        '''
        
        def optfun(w, x, y, d):
            hw=w/2
            l=x-hw
            b=y-hw
            r=x+hw
            t=y+hw
            return n-np.count_nonzero((l<d[0]) & (d[0]<r) & (b<d[1]) & (d[1]<t))
            
        d=self.dat[1]
        minW=0
        maxW=2*max(self.maxX-self.minX,self.maxY-self.minY)
        cx=min(cx,self.maxX)
        cx=max(cx,self.minX)
        cy=min(cy,self.maxY)
        cy=max(cy,self.minY)
        return cx, cy, bisect(optfun, minW, maxW, args=(cx,cy, d), xtol=10e-12)

class App(wx.App):

    def OnInit(self):
        'Create the main window and insert the custom frame'
        frame = CanvasFrame()
        frame.Show(True)

        return True


if __name__ == '__main__':


    app = App(False)
    app.MainLoop()

