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
import sys, os, math

import wx

import matplotlib

matplotlib.use('WXAgg')

from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg as NavToolbar
from matplotlib.backends.backend_wx import _load_bitmap, StatusBarWx

from matplotlib.figure import Figure
from matplotlib.widgets import RectangleSelector
from matplotlib.patches import Rectangle
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import rcParams


version = "1.0.6"

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
            self.eventpress.xdata=ev.xdata
            self.eventpress.ydata=ev.ydata
            ev.xdata+=self.wdata
            ev.ydata+=self.hdata
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
        self.selector.set_active(True)
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
               self.AddCheckTool(self.wx_ids[text], text, bitmap,
                                 shortHelp=text, longHelp=tooltip_text)
            else:
               self.AddTool(self.wx_ids[text], text, bitmap, tooltip_text)
            self.Bind(wx.EVT_TOOL, getattr(self, callback), id=self.wx_ids[text])

        self.ToggleTool(self.wx_ids['ROI'], True)
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
            dw = {  'C': (w-nw)/2,
                    'L': 0,
                    'R': w-nw
                }[self.canvas.parentFrame.anchorRB.GetStringSelection()[0]]
            self.roi.set_x(x+dw)
            self.roi.set_width(nw)
            self.updateCanvas()

    def onHeightChange(self, ev):
        if self.roi :
            y=self.roi.get_y()
            h=self.roi.get_height()
            nh=ev.GetValue()
            dh = {  'C': (h-nh)/2,
                    'B': 0,
                    'T': h-nh
                }[self.canvas.parentFrame.anchorRB.GetStringSelection()[-1]]
            self.roi.set_y(y+dh)
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
                            'Point Selector',
                            style = wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL )

        self.dirname=''
        self.filename=''
        self.exdirname=None
        self.SetFont(wx.Font(12 if wx.Platform == '__WXMAC__' else 11,
                                wx.FONTFAMILY_TELETYPE, wx.NORMAL, wx.NORMAL))


        # Setting up the menu.
        filemenu= wx.Menu()
        menuOpen = filemenu.Append(wx.ID_OPEN,
                    "&Open\tCTRL+O"," Open a data file")
        menuExport = filemenu.Append(wx.ID_SAVE,
                    "&Export selection\tCTRL+E"," Export selected data to a file.")
        menuAbout= filemenu.Append(wx.ID_ABOUT,
                    "About"," Information about this program")
        menuExit = filemenu.Append(wx.ID_EXIT,
                    "E&xit\tCTRL+X"," Terminate the program")

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
        self.conc = 0
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

        # Vertical sizer for canvas and controls
        self.sizer = wx.BoxSizer(wx.VERTICAL)

        # Scrolling controls panel
        self.ctrlPanel = wx.ScrolledWindow(self, wx.ID_ANY, style=wx.TAB_TRAVERSAL | wx.VSCROLL)
        # Build the side bar
        self.sideBar = wx.BoxSizer(wx.VERTICAL)
        heading = wx.StaticText(self.ctrlPanel, label='Measurements', )
        heading.SetFont(self.GetFont().MakeBold())
        self.sideBar.Add(heading, 0, wx.TOP | wx.ALIGN_CENTER)
        self.sideBar.Add(wx.StaticLine(self.ctrlPanel, size=(100,-1)), 0, wx.BOTTOM | wx.CENTER)
        self.sideBar.AddSpacer(3)
        self.positionDSP = wx.StaticText(self.ctrlPanel, style=wx.ALIGN_LEFT)
        self.sideBar.Add(self.positionDSP, 0, wx.BOTTOM | wx.LEFT)
        self.sideBar.AddSpacer(3)
        self.whDSP = wx.StaticText(self.ctrlPanel, style=wx.ALIGN_LEFT)
        self.sideBar.Add(self.whDSP, 0, wx.BOTTOM | wx.LEFT)
        self.sideBar.AddSpacer(3)
        self.areaDSP = wx.StaticText(self.ctrlPanel, style=wx.ALIGN_LEFT)
        self.sideBar.Add(self.areaDSP, 0, wx.BOTTOM | wx.LEFT)
        self.sideBar.AddSpacer(3)
        self.numberDSP = wx.StaticText(self.ctrlPanel, style=wx.ALIGN_LEFT)
        self.sideBar.Add(self.numberDSP, 0, wx.BOTTOM | wx.LEFT)
        self.sideBar.AddSpacer(3)
        self.concDSP = wx.StaticText(self.ctrlPanel, style=wx.ALIGN_LEFT)
        self.sideBar.Add(self.concDSP, 0, wx.BOTTOM | wx.LEFT)
        self.sideBar.AddSpacer(3)
        self.sideBar.Add(wx.StaticLine(self.ctrlPanel,size=(100,-1)), 0, wx.BOTTOM | wx.CENTER)

        self.sideBar.AddSpacer(9)

        self.titleCtrl = wx.TextCtrl(self.ctrlPanel, value='', size=(120,-1))
        self.sideBar.Add(wx.StaticText(self.ctrlPanel, label='Title:', style=wx.ALIGN_LEFT), 0, wx.LEFT)
        self.sideBar.Add(self.titleCtrl, 0, wx.EXPAND)

        self.sideBar.AddSpacer(5)

        self.widthCtrl = wx.SpinCtrlDouble(self.ctrlPanel, min=0, initial=0, inc=1)
        self.heightCtrl = wx.SpinCtrlDouble(self.ctrlPanel, min=0, initial=0, inc=1)
        self.widthCtrl.SetDigits(2)
        self.heightCtrl.SetDigits(2)
        self.fixedSizeCB = wx.CheckBox(self.ctrlPanel, label='Fixed size', style=wx.ALIGN_LEFT)

        box = wx.StaticBoxSizer(wx.StaticBox(self.ctrlPanel, label='Size (um):'),wx.VERTICAL)
        box.Add(self.fixedSizeCB,0, wx.LEFT)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(wx.StaticText(self.ctrlPanel, label='W:', style=wx.ALIGN_RIGHT), 0, wx.CENTER)
        hbox.Add(self.widthCtrl, 0, wx.LEFT)
        box.Add(hbox, 0, wx.TOP | wx.LEFT)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(wx.StaticText(self.ctrlPanel, label='H:', style=wx.ALIGN_RIGHT), 0, wx.CENTER)
        hbox.Add(self.heightCtrl, 0, wx.LEFT)
        box.Add(hbox, 0, wx.TOP | wx.LEFT)
        self.sideBar.Add(box, 0, wx.LEFT)

        self.sideBar.AddSpacer(5)

        self.fixedNumberCB = wx.CheckBox(self.ctrlPanel, label='Fixed nr.', style=wx.ALIGN_LEFT)
        self.numPtsCtrl = wx.SpinCtrl(self.ctrlPanel, min=0, max=1000, initial=0)
        self.numPtsCtrl.Disable()
        box = wx.StaticBoxSizer(wx.StaticBox(self.ctrlPanel, label='# Points:'),wx.VERTICAL)
        box.Add(self.fixedNumberCB,0, wx.LEFT)
        box.Add(self.numPtsCtrl, 0, wx.EXPAND)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        box.Add(hbox, 1, wx.EXPAND)
        self.sideBar.Add(box, 0, wx.LEFT | wx.EXPAND)

        self.sideBar.AddSpacer(5)

        # Anchor switch
        self.anchorRB = wx.RadioBox(self.ctrlPanel, label='Anchor:',
                                    choices=['LT','L','LB','T','C','B','RT','R','RB'],
                                    majorDimension=3,
                                    style= wx.RA_SPECIFY_ROWS)
        # Center is default
        self.anchorRB.SetSelection(4)
        for i in [1,3,5,7] : self.anchorRB.ShowItem(i,False)
        self.sideBar.Add(self.anchorRB, 0, wx.BOTTOM | wx.LEFT | wx.EXPAND)

        self.sideBar.AddSpacer(9)
        # Flip buttons
        box = wx.StaticBoxSizer(wx.StaticBox(self.ctrlPanel, label='Flip data:'),wx.HORIZONTAL)
        self.flipXBTN=wx.BitmapButton(self.ctrlPanel, bitmap=wx.Bitmap('flip_x.png'))
        self.flipYBTN=wx.BitmapButton(self.ctrlPanel, bitmap=wx.Bitmap('flip_y.png'))
        box.Add(wx.StaticText(self.ctrlPanel, label='X:', style=wx.ALIGN_LEFT), 0, wx.CENTER )
        box.Add(self.flipXBTN, 0, wx.LEFT)
        box.Add(wx.StaticText(self.ctrlPanel, label=' Y:', style=wx.ALIGN_LEFT), 0, wx.CENTER )
        box.Add(self.flipYBTN, 0, wx.LEFT)
        self.sideBar.Add(box, 0, wx.LEFT | wx.EXPAND)

        self.sideBar.AddSpacer(9)
        # Aspect ratio switch
        self.aspectRB = wx.RadioBox(self.ctrlPanel, label='Aspect ratio:',
                                    choices=['auto','equal'],)
        # Auto is default
        self.aspectRB.SetSelection(0)
        self.sideBar.Add(self.aspectRB, 0, wx.BOTTOM | wx.LEFT | wx.EXPAND)

        # Final Spacer
        self.sideBar.AddStretchSpacer()

        # Set sizer inside the ctrlPanel
        self.ctrlPanel.SetSizer(self.sideBar)
        self.ctrlPanel.FitInside()
        self.ctrlPanel.SetScrollRate(0,5)

        # Build the window

        # Add plot canvas and sidebar
        cont=wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(cont, 1, wx.TOP | wx.LEFT | wx.EXPAND)
        cont.Add(self.canvas, 1, wx.TOP | wx.LEFT | wx.EXPAND)
        cont.AddSpacer(3)
        cont.Add(self.ctrlPanel, 0, wx.TOP | wx.RIGHT | wx.EXPAND)
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
        self.aspectRB.Bind(wx.EVT_RADIOBOX, self.onAspectChange)

        if self.toolbar is not None:
            self.toolbar.Realize()
            # Default window size is incorrect, so set
            # toolbar width to figure width.
            tw, th = self.toolbar.GetSize()
            fw, fh = self.canvas.GetSize()
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
            #self.datfn='data/A339-SiC-560-1-SiC-WDS.txt'
            pass

        try :
            self.dirname, self.filename=os.path.split(self.datfn)
            self.dat=self.readData(self.datfn)
            self.displayData(self.dat[1],self.dat[0])
            self.axes.set_title(self.filename)
        except IOError :
            if self.datfn!='' :
                print('Warning: Cannot open file ', self.datfn)

        self.titleCtrl.SetValue(self.filename)
        self.redrawPlot()

        # Init sidebar
        self.showLTRB()
        self.showWH()
        self.showArea()
        self.showNumber()
        self.showConc()

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
        #print(df)
        #print(df[0].strip())
        # The translation replaces ; and , by space and dot.
        if skip>0 :
            lbl=df[0].replace('#','').strip().split(';')
        else :
            lbl=None
        r = [lbl, array([[float(v)
                            for v in  ln.replace(';',' ').replace(',','.').split()]
                                for ln in df[skip:] if ln[0]!='#' and ln.split()]).T]
        d=r[1]
        #print(d, d.shape)
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
        try :
            x, y = self.toolbar.roi.get_xy()
            w = self.toolbar.roi.get_width()
            h = self.toolbar.roi.get_height()
            hdr += '\n'
            hdr += (' ROI (um): X=%.2f  Y=%.2f  W=%.2f  H=%.2f    Points=%d   Concentration=%g'
                        % (x, y, w,h, sel.shape[1],sum(sel[2])/(w*h)) )
        except AttributeError :
            # No roi
            pass
        if sel is None :
            wx.MessageBox('Nothing to save yet. Make some selection before trying to export data.',
                            'Nothing to export!')
        else :
            d=array(sel)
            # Shift exported data to the origin
            d[0]-=min(d[0])
            d[1]-=min(d[1])
            np.savetxt(fn, d.T, fmt='%11.3f', delimiter=' ', newline='\n',
                header=hdr, footer='', comments='#')


    def setLimits(self):
        self.widthCtrl.SetMax(self.maxX-self.minX)
        self.heightCtrl.SetMax(self.maxY-self.minY)
        self.numPtsCtrl.SetRange(0,self.numPoints)

    def showArea(self, a=0):
        self.areaDSP.SetLabel('Area (um^2):  \n %-8g' % (a))

    def showLTRB(self, l=0, t=0, r=0, b=0):
        self.positionDSP.SetLabel(u'Position (um):  \n L: %-8g\n T: %-8g\n R: %-8g\n B: %-8g' % (l,t,r,b))

    def showWH(self, w=0, h=0):
        self.whDSP.SetLabel('Size (um):  \n W: %-8g\n H: %-8g' % (w, h))

    def showNumber(self, n=0):
        self.numberDSP.SetLabel('Selected pnts: \n %-d' % (n))

    def showConc(self, g=0):
        self.concDSP.SetLabel('Concentration: \n %.3f' % (g))

    def showROI(self, x, y, w, h):
        self.showLTRB(l=x,t=y+h,r=x+w,b=y)
        self.showArea(w*h)
        self.showWH(w,h)

    def setWH(self, w, h):
        self.widthCtrl.SetValue(w)
        self.heightCtrl.SetValue(h)
        self.showArea(w*h)
        self.showWH(w,h)
        try :
            sel=self.getSelected()
            self.numSelected=sel.shape[1]
            self.conc=sum(sel[2])/(w*h)
        except AttributeError :
            self.numSelected=0
            self.conc=0.0
        if not self.fixedNumberCB.IsChecked() :
            self.numPtsCtrl.SetValue(self.numSelected)
        self.showNumber(self.numSelected)
        self.showConc(self.conc)

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
        dlg = wx.MessageDialog(self,
                                "ROI selector\nVersion %s" % (version),
                                "About PointSel", wx.OK)
        dlg.ShowModal() # Shows it
        dlg.Destroy() # finally destroy it when finished.

    def onExit(self,e):
        self.Close(True)  # Close the frame.

    def onOpen(self,e):
        """ Open a file"""
        dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "*.*", wx.FD_OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.filename = dlg.GetFilename()
            self.dirname = dlg.GetDirectory()
            self.datfn=os.path.join(self.dirname, self.filename)
            try :
                self.dat=self.readData(self.datfn)
                self.displayData(self.dat[1],self.dat[0])
                w, h = self.maxX/20, self.maxY/20
                self.updateROI(self.maxX/2, self.maxY/2,
                               self.maxX/20, self.maxY/20)
                self.axes.set_xlim(0,self.maxX)
                self.axes.set_ylim(0,self.maxY)
                self.toolbar.update()
                self.toolbar.push_current()
                self.redrawPlot()
            except (IOError, IndexError, ValueError) as ex :
                wx.MessageBox('The data from:\n\n'
                              + self.datfn
                              + '\n\ncould not be read properly.'
                              + '\nProbably the format is incorrect.',
                              'Error reading data')
        dlg.Destroy()

    def onPaint(self, event):
        self.canvas.draw()

    def onExport(self, e):
        '''Export the selected points'''
        if self.exdirname is None :
            self.exdirname = self.dirname
        dlg = wx.FileDialog(self, "Choose a file", self.exdirname, "*.txt",
                                "Data file (*.txt)|*.txt|"+
                                "Data file (*.dat)|*.dat|"+
                                "All files (*.*)|*.*",
                                wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:
            # The file name is local here.
            # We are saving a selection not the data.
            filename = dlg.GetFilename()
            self.exdirname = dlg.GetDirectory()
            self.exportData(os.path.join(self.exdirname, filename))
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
        self.showLTRB(l=x,t=y+h,r=x+w,b=y)
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
        pass
        #s=self.anchorRB.GetSelection()
        #print(self.anchorRB.GetString(s))

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

    def onAspectChange(self, ev):
        s=self.aspectRB.GetString(self.aspectRB.GetSelection())
        self.axes.set_aspect(s,'datalim')
        if s=='auto':
            self.axes.set_xlim(0,self.maxX)
            self.axes.set_ylim(0,self.maxY)
        self.redrawPlot()

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
        ncx, ncy, tw=self.findROIforN(x, y, w, h, n,
                        self.anchorRB.GetString(self.anchorRB.GetSelection()))
        #print('ROIforN:',cx,cy,tw)
        self.updateROI(ncx,ncy,tw,tw)
        self.setWH(tw,tw)

    def findROIforN(self, x, y, w, h, n, fp='C'):
        '''
        Find the squere ROI around target point (cx, cy) containing
        as close as possible to target number of points (n).
        The function does not care about the GUI. Just the computation.
        '''

        def optfunC(w, x, y, d):
            hw=w/2
            l=x-hw
            b=y-hw
            r=x+hw
            t=y+hw
            return n-np.count_nonzero((l<d[0]) & (d[0]<r) & (b<d[1]) & (d[1]<t))

        def optfunLB(w, x, y, d):
            l=x
            b=y
            r=x+w
            t=y+w
            return n-np.count_nonzero((l<d[0]) & (d[0]<r) & (b<d[1]) & (d[1]<t))

        def optfunLT(w, x, y, d):
            l=x
            b=y-w
            r=x+w
            t=y
            return n-np.count_nonzero((l<d[0]) & (d[0]<r) & (b<d[1]) & (d[1]<t))

        def optfunRT(w, x, y, d):
            l=x-w
            b=y-w
            r=x
            t=y
            return n-np.count_nonzero((l<d[0]) & (d[0]<r) & (b<d[1]) & (d[1]<t))

        def optfunRB(w, x, y, d):
            l=x-w
            b=y
            r=x
            t=y+w
            return n-np.count_nonzero((l<d[0]) & (d[0]<r) & (b<d[1]) & (d[1]<t))

        optfun={'C': optfunC,
                'LB': optfunLB,
                'LT': optfunLT,
                'RB': optfunRB,
                'RT': optfunRT }

        #print(fp)
        d=self.dat[1]
        minW=0
        maxW=2*max(self.maxX-self.minX,self.maxY-self.minY)
        if fp=='C' :
            cx=x+w/2 ; cy=y+h/2
        elif fp=='LB' :
            cx=x ; cy=y
        elif fp=='LT' :
            cx=x ; cy=y+h
        elif fp=='RT' :
            cx=x+w ; cy=y+h
        elif fp=='RB' :
            cx=x+w ; cy=y
        else :
            print('This should not happen! Inform the author')

        cx=min(cx,self.maxX)
        cx=max(cx,self.minX)
        cy=min(cy,self.maxY)
        cy=max(cy,self.minY)

        try :
            nw=bisect(optfun[fp], minW, maxW, args=(cx,cy, d), xtol=10e-12)
        except ValueError :
            #wx.MessageBox('Cannot find a good solution for the selection box. ',
            #                'Solver error!')
            return x, y, math.sqrt(w*h)

        if fp=='C' :
            cx-=nw/2 ; cy-=nw/2
        elif fp=='LB' :
            pass
        elif fp=='LT' :
            cy-=nw
        elif fp=='RT' :
            cx-=nw ; cy-=nw
        elif fp=='RB' :
            cx-=nw
        else :
            print('This should not happen! Inform the author')
        return cx, cy, nw

class App(wx.App):

    def OnInit(self):
        'Create the main window and insert the custom frame'
        frame = CanvasFrame()
        frame.Show(True)

        return True


    def MacOpenFile(self, filename):
        print(filename)

if __name__ == '__main__':


    app = App(False)
    app.MainLoop()
