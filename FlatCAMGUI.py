from PyQt4 import QtGui, QtCore, Qt
from GUIElements import *

class FlatCAMGUI(QtGui.QMainWindow):

    def __init__(self):
        super(FlatCAMGUI, self).__init__()

        # Divine icon pack by Ipapun @ finicons.com

        ############
        ### Menu ###
        ############
        self.menu = self.menuBar()

        ### File ###
        self.menufile = self.menu.addMenu('&File')

        # New
        self.menufilenew = QtGui.QAction(QtGui.QIcon('share/file16.png'), '&New', self)
        self.menufile.addAction(self.menufilenew)
        # Open recent

        # Recent
        self.recent = self.menufile.addMenu(QtGui.QIcon('share/folder16.png'), "Open recent ...")

        # Open gerber
        self.menufileopengerber = QtGui.QAction(QtGui.QIcon('share/folder16.png'), 'Open &Gerber ...', self)
        self.menufile.addAction(self.menufileopengerber)

        # Open Excellon ...
        self.menufileopenexcellon = QtGui.QAction(QtGui.QIcon('share/folder16.png'), 'Open &Excellon ...', self)
        self.menufile.addAction(self.menufileopenexcellon)

        # Open G-Code ...
        self.menufileopengcode = QtGui.QAction(QtGui.QIcon('share/folder16.png'), 'Open G-&Code ...', self)
        self.menufile.addAction(self.menufileopengcode)

        # Open Project ...
        self.menufileopenproject = QtGui.QAction(QtGui.QIcon('share/folder16.png'), 'Open &Project ...', self)
        self.menufileopenproject.setShortcuts(QtGui.QKeySequence.Open)
        self.menufile.addAction(self.menufileopenproject)

        # Save Project
        self.menufilesaveproject = QtGui.QAction(QtGui.QIcon('share/floppy16.png'), '&Save Project', self)
        self.menufilesaveproject.setShortcuts(QtGui.QKeySequence.Save)
        self.menufile.addAction(self.menufilesaveproject)

        # Save Project As ...
        self.menufilesaveprojectas = QtGui.QAction(QtGui.QIcon('share/floppy16.png'), 'Save Project &As ...', self)
        self.menufilesaveprojectas.setShortcuts(QtGui.QKeySequence.SaveAs)
        self.menufile.addAction(self.menufilesaveprojectas)

        # Save Project Copy ...
        self.menufilesaveprojectcopy = QtGui.QAction(QtGui.QIcon('share/floppy16.png'), 'Save Project C&opy ...', self)
        self.menufile.addAction(self.menufilesaveprojectcopy)

        # Save Defaults
        self.menufilesavedefaults = QtGui.QAction(QtGui.QIcon('share/floppy16.png'), 'Save &Defaults', self)
        self.menufile.addAction(self.menufilesavedefaults)

        # Quit
        exit_action = QtGui.QAction(QtGui.QIcon('share/power16.png'), '&Exit', self)
        # exitAction.setShortcut('Ctrl+Q')
        # exitAction.setStatusTip('Exit application')
        exit_action.triggered.connect(QtGui.qApp.quit)

        self.menufile.addAction(exit_action)

        ### Edit ###
        self.menuedit = self.menu.addMenu('&Edit')
        self.menueditdelete = self.menuedit.addAction(QtGui.QIcon('share/trash16.png'), 'Delete')

        ### Options ###
        self.menuoptions = self.menu.addMenu('&Options')
        self.menuoptions_transfer = self.menuoptions.addMenu('Transfer options')
        self.menuoptions_transfer_a2p = self.menuoptions_transfer.addAction("Application to Project")
        self.menuoptions_transfer_p2a = self.menuoptions_transfer.addAction("Project to Application")
        self.menuoptions_transfer_p2o = self.menuoptions_transfer.addAction("Project to Object")
        self.menuoptions_transfer_o2p = self.menuoptions_transfer.addAction("Object to Project")
        self.menuoptions_transfer_a2o = self.menuoptions_transfer.addAction("Application to Object")
        self.menuoptions_transfer_o2a = self.menuoptions_transfer.addAction("Object to Application")

        ### View ###
        self.menuview = self.menu.addMenu('&View')
        self.menuviewdisableall = self.menuview.addAction(QtGui.QIcon('share/clear_plot16.png'), 'Disable all plots')
        self.menuviewdisableother = self.menuview.addAction(QtGui.QIcon('share/clear_plot16.png'),
                                                            'Disable all plots but this one')
        self.menuviewenable = self.menuview.addAction(QtGui.QIcon('share/replot16.png'), 'Enable all plots')

        ### Tool ###
        self.menutool = self.menu.addMenu('&Tool')

        ### Help ###
        self.menuhelp = self.menu.addMenu('&Help')
        self.menuhelp_about = self.menuhelp.addAction(QtGui.QIcon('share/tv16.png'), 'About FlatCAM')
        self.menuhelp_manual = self.menuhelp.addAction(QtGui.QIcon('share/globe16.png'), 'Manual')

        ###############
        ### Toolbar ###
        ###############
        self.toolbar = QtGui.QToolBar()
        self.addToolBar(self.toolbar)

        self.zoom_fit_btn = self.toolbar.addAction(QtGui.QIcon('share/zoom_fit32.png'), "&Zoom Fit")
        self.zoom_out_btn = self.toolbar.addAction(QtGui.QIcon('share/zoom_out32.png'), "&Zoom Out")
        self.zoom_in_btn = self.toolbar.addAction(QtGui.QIcon('share/zoom_in32.png'), "&Zoom In")
        self.clear_plot_btn = self.toolbar.addAction(QtGui.QIcon('share/clear_plot32.png'), "&Clear Plot")
        self.replot_btn = self.toolbar.addAction(QtGui.QIcon('share/replot32.png'), "&Replot")
        self.delete_btn = self.toolbar.addAction(QtGui.QIcon('share/delete32.png'), "&Delete")

        ################
        ### Splitter ###
        ################
        self.splitter = QtGui.QSplitter()
        self.setCentralWidget(self.splitter)

        ################
        ### Notebook ###
        ################
        self.notebook = QtGui.QTabWidget()
        # self.notebook.setMinimumWidth(250)

        ### Projet ###
        project_tab = QtGui.QWidget()
        project_tab.setMinimumWidth(250)  # Hack
        self.project_tab_layout = QtGui.QVBoxLayout(project_tab)
        self.project_tab_layout.setContentsMargins(2, 2, 2, 2)
        self.notebook.addTab(project_tab, "Project")

        ### Selected ###
        self.selected_tab = QtGui.QWidget()
        self.selected_tab_layout = QtGui.QVBoxLayout(self.selected_tab)
        self.selected_tab_layout.setContentsMargins(2, 2, 2, 2)
        self.selected_scroll_area = VerticalScrollArea()
        self.selected_tab_layout.addWidget(self.selected_scroll_area)
        self.notebook.addTab(self.selected_tab, "Selected")

        ### Options ###
        self.options_tab = QtGui.QWidget()
        self.options_tab.setContentsMargins(0, 0, 0, 0)
        self.options_tab_layout = QtGui.QVBoxLayout(self.options_tab)
        self.options_tab_layout.setContentsMargins(2, 2, 2, 2)

        hlay1 = QtGui.QHBoxLayout()
        self.options_tab_layout.addLayout(hlay1)

        self.icon = QtGui.QLabel()
        self.icon.setPixmap(QtGui.QPixmap('share/gear48.png'))
        hlay1.addWidget(self.icon)

        self.options_combo = QtGui.QComboBox()
        self.options_combo.addItem("APPLICATION DEFAULTS")
        self.options_combo.addItem("PROJECT OPTIONS")
        hlay1.addWidget(self.options_combo)
        hlay1.addStretch()

        self.options_scroll_area = VerticalScrollArea()
        self.options_tab_layout.addWidget(self.options_scroll_area)

        self.notebook.addTab(self.options_tab, "Options")

        ### Tool ###
        self.tool_tab = QtGui.QWidget()
        self.tool_tab_layout = QtGui.QVBoxLayout(self.tool_tab)
        self.tool_tab_layout.setContentsMargins(2, 2, 2, 2)
        self.notebook.addTab(self.tool_tab, "Tool")
        self.tool_scroll_area = VerticalScrollArea()
        self.tool_tab_layout.addWidget(self.tool_scroll_area)

        self.splitter.addWidget(self.notebook)

        ######################
        ### Plot and other ###
        ######################
        right_widget = QtGui.QWidget()
        # right_widget.setContentsMargins(0, 0, 0, 0)
        self.splitter.addWidget(right_widget)
        self.right_layout = QtGui.QVBoxLayout()
        self.right_layout.setMargin(0)
        # self.right_layout.setContentsMargins(0, 0, 0, 0)
        right_widget.setLayout(self.right_layout)


        ################
        ### Info bar ###
        ################
        infobar = self.statusBar()

        self.info_label = QtGui.QLabel("Welcome to FlatCAM.")
        self.info_label.setFrameStyle(QtGui.QFrame.StyledPanel | QtGui.QFrame.Plain)
        infobar.addWidget(self.info_label, stretch=1)

        self.position_label = QtGui.QLabel("")
        self.position_label.setFrameStyle(QtGui.QFrame.StyledPanel | QtGui.QFrame.Plain)
        self.position_label.setMinimumWidth(110)
        infobar.addWidget(self.position_label)

        self.units_label = QtGui.QLabel("[in]")
        # self.units_label.setFrameStyle(QtGui.QFrame.StyledPanel | QtGui.QFrame.Plain)
        self.units_label.setMargin(2)
        infobar.addWidget(self.units_label)

        self.progress_bar = QtGui.QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        infobar.addWidget(self.progress_bar)

        #############
        ### Icons ###
        #############
        self.app_icon = QtGui.QIcon()
        self.app_icon.addFile('share/flatcam_icon16.png', QtCore.QSize(16, 16))
        self.app_icon.addFile('share/flatcam_icon24.png', QtCore.QSize(24, 24))
        self.app_icon.addFile('share/flatcam_icon32.png', QtCore.QSize(32, 32))
        self.app_icon.addFile('share/flatcam_icon48.png', QtCore.QSize(48, 48))
        self.app_icon.addFile('share/flatcam_icon128.png', QtCore.QSize(128, 128))
        self.app_icon.addFile('share/flatcam_icon256.png', QtCore.QSize(256, 256))
        self.setWindowIcon(self.app_icon)

        self.setGeometry(100, 100, 1024, 650)
        self.setWindowTitle('FlatCAM - Alpha 5')
        self.show()


class OptionsGroupUI(QtGui.QGroupBox):
    def __init__(self, title, parent=None):
        QtGui.QGroupBox.__init__(self, title, parent=parent)
        self.setStyleSheet("""
        QGroupBox
        {
            font-size: 16px;
            font-weight: bold;
        }
        """)

        self.layout = QtGui.QVBoxLayout()
        self.setLayout(self.layout)


class GerberOptionsGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        OptionsGroupUI.__init__(self, "Gerber Options", parent=parent)

        ## Plot options
        self.plot_options_label = QtGui.QLabel("<b>Plot Options:</b>")
        self.layout.addWidget(self.plot_options_label)

        grid0 = QtGui.QGridLayout()
        self.layout.addLayout(grid0)
        # Plot CB
        self.plot_cb = FCCheckBox(label='Plot')
        self.plot_options_label.setToolTip(
            "Plot (show) this object."
        )
        grid0.addWidget(self.plot_cb, 0, 0)

        # Solid CB
        self.solid_cb = FCCheckBox(label='Solid')
        self.solid_cb.setToolTip(
            "Solid color polygons."
        )
        grid0.addWidget(self.solid_cb, 0, 1)

        # Multicolored CB
        self.multicolored_cb = FCCheckBox(label='Multicolored')
        self.multicolored_cb.setToolTip(
            "Draw polygons in different colors."
        )
        grid0.addWidget(self.multicolored_cb, 0, 2)

        ## Isolation Routing
        self.isolation_routing_label = QtGui.QLabel("<b>Isolation Routing:</b>")
        self.isolation_routing_label.setToolTip(
            "Create a Geometry object with\n"
            "toolpaths to cut outside polygons."
        )
        self.layout.addWidget(self.isolation_routing_label)

        grid1 = QtGui.QGridLayout()
        self.layout.addLayout(grid1)
        tdlabel = QtGui.QLabel('Tool dia:')
        tdlabel.setToolTip(
            "Diameter of the cutting tool."
        )
        grid1.addWidget(tdlabel, 0, 0)
        self.iso_tool_dia_entry = LengthEntry()
        grid1.addWidget(self.iso_tool_dia_entry, 0, 1)

        passlabel = QtGui.QLabel('Width (# passes):')
        passlabel.setToolTip(
            "Width of the isolation gap in\n"
            "number (integer) of tool widths."
        )
        grid1.addWidget(passlabel, 1, 0)
        self.iso_width_entry = IntEntry()
        grid1.addWidget(self.iso_width_entry, 1, 1)

        overlabel = QtGui.QLabel('Pass overlap:')
        overlabel.setToolTip(
            "How much (fraction of tool width)\n"
            "to overlap each pass."
        )
        grid1.addWidget(overlabel, 2, 0)
        self.iso_overlap_entry = FloatEntry()
        grid1.addWidget(self.iso_overlap_entry, 2, 1)

        ## Board cuttout
        self.board_cutout_label = QtGui.QLabel("<b>Board cutout:</b>")
        self.board_cutout_label.setToolTip(
            "Create toolpaths to cut around\n"
            "the PCB and separate it from\n"
            "the original board."
        )
        self.layout.addWidget(self.board_cutout_label)

        grid2 = QtGui.QGridLayout()
        self.layout.addLayout(grid2)
        tdclabel = QtGui.QLabel('Tool dia:')
        tdclabel.setToolTip(
            "Diameter of the cutting tool."
        )
        grid2.addWidget(tdclabel, 0, 0)
        self.cutout_tooldia_entry = LengthEntry()
        grid2.addWidget(self.cutout_tooldia_entry, 0, 1)

        marginlabel = QtGui.QLabel('Margin:')
        marginlabel.setToolTip(
            "Distance from objects at which\n"
            "to draw the cutout."
        )
        grid2.addWidget(marginlabel, 1, 0)
        self.cutout_margin_entry = LengthEntry()
        grid2.addWidget(self.cutout_margin_entry, 1, 1)

        gaplabel = QtGui.QLabel('Gap size:')
        gaplabel.setToolTip(
            "Size of the gaps in the toolpath\n"
            "that will remain to hold the\n"
            "board in place."
        )
        grid2.addWidget(gaplabel, 2, 0)
        self.cutout_gap_entry = LengthEntry()
        grid2.addWidget(self.cutout_gap_entry, 2, 1)

        gapslabel = QtGui.QLabel('Gaps:')
        gapslabel.setToolTip(
            "Where to place the gaps, Top/Bottom\n"
            "Left/Rigt, or on all 4 sides."
        )
        grid2.addWidget(gapslabel, 3, 0)
        self.gaps_radio = RadioSet([{'label': '2 (T/B)', 'value': 'tb'},
                                    {'label': '2 (L/R)', 'value': 'lr'},
                                    {'label': '4', 'value': '4'}])
        grid2.addWidget(self.gaps_radio, 3, 1)

        ## Non-copper regions
        self.noncopper_label = QtGui.QLabel("<b>Non-copper regions:</b>")
        self.noncopper_label.setToolTip(
            "Create polygons covering the\n"
            "areas without copper on the PCB.\n"
            "Equivalent to the inverse of this\n"
            "object. Can be used to remove all\n"
            "copper from a specified region."
        )
        self.layout.addWidget(self.noncopper_label)

        grid3 = QtGui.QGridLayout()
        self.layout.addLayout(grid3)

        # Margin
        bmlabel = QtGui.QLabel('Boundary Margin:')
        bmlabel.setToolTip(
            "Specify the edge of the PCB\n"
            "by drawing a box around all\n"
            "objects with this minimum\n"
            "distance."
        )
        grid3.addWidget(bmlabel, 0, 0)
        self.noncopper_margin_entry = LengthEntry()
        grid3.addWidget(self.noncopper_margin_entry, 0, 1)

        # Rounded corners
        self.noncopper_rounded_cb = FCCheckBox(label="Rounded corners")
        self.noncopper_rounded_cb.setToolTip(
            "Creates a Geometry objects with polygons\n"
            "covering the copper-free areas of the PCB."
        )
        grid3.addWidget(self.noncopper_rounded_cb, 1, 0, 1, 2)

        ## Bounding box
        self.boundingbox_label = QtGui.QLabel('<b>Bounding Box:</b>')
        self.layout.addWidget(self.boundingbox_label)

        grid4 = QtGui.QGridLayout()
        self.layout.addLayout(grid4)

        bbmargin = QtGui.QLabel('Boundary Margin:')
        bbmargin.setToolTip(
            "Distance of the edges of the box\n"
            "to the nearest polygon."
        )
        grid4.addWidget(bbmargin, 0, 0)
        self.bbmargin_entry = LengthEntry()
        grid4.addWidget(self.bbmargin_entry, 0, 1)

        self.bbrounded_cb = FCCheckBox(label="Rounded corners")
        self.bbrounded_cb.setToolTip(
            "If the bounding box is \n"
            "to have rounded corners\n"
            "their radius is equal to\n"
            "the margin."
        )
        grid4.addWidget(self.bbrounded_cb, 1, 0, 1, 2)


class ExcellonOptionsGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        OptionsGroupUI.__init__(self, "Excellon Options", parent=parent)

        ## Plot options
        self.plot_options_label = QtGui.QLabel("<b>Plot Options:</b>")
        self.layout.addWidget(self.plot_options_label)

        grid0 = QtGui.QGridLayout()
        self.layout.addLayout(grid0)
        self.plot_cb = FCCheckBox(label='Plot')
        self.plot_cb.setToolTip(
            "Plot (show) this object."
        )
        grid0.addWidget(self.plot_cb, 0, 0)
        self.solid_cb = FCCheckBox(label='Solid')
        self.solid_cb.setToolTip(
            "Solid circles."
        )
        grid0.addWidget(self.solid_cb, 0, 1)

        ## Create CNC Job
        self.cncjob_label = QtGui.QLabel('<b>Create CNC Job</b>')
        self.cncjob_label.setToolTip(
            "Create a CNC Job object\n"
            "for this drill object."
        )
        self.layout.addWidget(self.cncjob_label)

        grid1 = QtGui.QGridLayout()
        self.layout.addLayout(grid1)

        cutzlabel = QtGui.QLabel('Cut Z:')
        cutzlabel.setToolTip(
            "Drill depth (negative)\n"
            "below the copper surface."
        )
        grid1.addWidget(cutzlabel, 0, 0)
        self.cutz_entry = LengthEntry()
        grid1.addWidget(self.cutz_entry, 0, 1)

        travelzlabel = QtGui.QLabel('Travel Z:')
        travelzlabel.setToolTip(
            "Tool height when travelling\n"
            "across the XY plane."
        )
        grid1.addWidget(travelzlabel, 1, 0)
        self.travelz_entry = LengthEntry()
        grid1.addWidget(self.travelz_entry, 1, 1)

        frlabel = QtGui.QLabel('Feed rate:')
        frlabel.setToolTip(
            "Tool speed while drilling\n"
            "(in units per minute)."
        )
        grid1.addWidget(frlabel, 2, 0)
        self.feedrate_entry = LengthEntry()
        grid1.addWidget(self.feedrate_entry, 2, 1)


class GeometryOptionsGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        OptionsGroupUI.__init__(self, "Geometry Options", parent=parent)

        ## Plot options
        self.plot_options_label = QtGui.QLabel("<b>Plot Options:</b>")
        self.layout.addWidget(self.plot_options_label)

        # Plot CB
        self.plot_cb = FCCheckBox(label='Plot')
        self.plot_cb.setToolTip(
            "Plot (show) this object."
        )
        self.layout.addWidget(self.plot_cb)

        ## Create CNC Job
        self.cncjob_label = QtGui.QLabel('<b>Create CNC Job:</b>')
        self.cncjob_label.setToolTip(
            "Create a CNC Job object\n"
            "tracing the contours of this\n"
            "Geometry object."
        )
        self.layout.addWidget(self.cncjob_label)

        grid1 = QtGui.QGridLayout()
        self.layout.addLayout(grid1)

        cutzlabel = QtGui.QLabel('Cut Z:')
        cutzlabel.setToolTip(
            "Cutting depth (negative)\n"
            "below the copper surface."
        )
        grid1.addWidget(cutzlabel, 0, 0)
        self.cutz_entry = LengthEntry()
        grid1.addWidget(self.cutz_entry, 0, 1)

        # Travel Z
        travelzlabel = QtGui.QLabel('Travel Z:')
        travelzlabel.setToolTip(
            "Height of the tool when\n"
            "moving without cutting."
        )
        grid1.addWidget(travelzlabel, 1, 0)
        self.travelz_entry = LengthEntry()
        grid1.addWidget(self.travelz_entry, 1, 1)

        # Feedrate
        frlabel = QtGui.QLabel('Feed Rate:')
        frlabel.setToolTip(
            "Cutting speed in the XY\n"
            "plane in units per minute"
        )
        grid1.addWidget(frlabel, 2, 0)
        self.cncfeedrate_entry = LengthEntry()
        grid1.addWidget(self.cncfeedrate_entry, 2, 1)

        # Tooldia
        tdlabel = QtGui.QLabel('Tool dia:')
        tdlabel.setToolTip(
            "The diameter of the cutting\n"
            "tool (just for display)."
        )
        grid1.addWidget(tdlabel, 3, 0)
        self.cnctooldia_entry = LengthEntry()
        grid1.addWidget(self.cnctooldia_entry, 3, 1)

        ## Paint area
        self.paint_label = QtGui.QLabel('<b>Paint Area:</b>')
        self.paint_label.setToolTip(
            "Creates tool paths to cover the\n"
            "whole area of a polygon (remove\n"
            "all copper). You will be asked\n"
            "to click on the desired polygon."
        )
        self.layout.addWidget(self.paint_label)

        grid2 = QtGui.QGridLayout()
        self.layout.addLayout(grid2)

        # Tool dia
        ptdlabel = QtGui.QLabel('Tool dia:')
        ptdlabel.setToolTip(
            "Diameter of the tool to\n"
            "be used in the operation."
        )
        grid2.addWidget(ptdlabel, 0, 0)

        self.painttooldia_entry = LengthEntry()
        grid2.addWidget(self.painttooldia_entry, 0, 1)

        # Overlap
        ovlabel = QtGui.QLabel('Overlap:')
        ovlabel.setToolTip(
            "How much (fraction) of the tool\n"
            "width to overlap each tool pass."
        )
        grid2.addWidget(ovlabel, 1, 0)
        self.paintoverlap_entry = LengthEntry()
        grid2.addWidget(self.paintoverlap_entry, 1, 1)

        # Margin
        marginlabel = QtGui.QLabel('Margin:')
        marginlabel.setToolTip(
            "Distance by which to avoid\n"
            "the edges of the polygon to\n"
            "be painted."
        )
        grid2.addWidget(marginlabel, 2, 0)
        self.paintmargin_entry = LengthEntry()
        grid2.addWidget(self.paintmargin_entry)


class CNCJobOptionsGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        OptionsGroupUI.__init__(self, "CNC Job Options", parent=None)

        ## Plot options
        self.plot_options_label = QtGui.QLabel("<b>Plot Options:</b>")
        self.layout.addWidget(self.plot_options_label)

        grid0 = QtGui.QGridLayout()
        self.layout.addLayout(grid0)

        # Plot CB
        # self.plot_cb = QtGui.QCheckBox('Plot')
        self.plot_cb = FCCheckBox('Plot')
        self.plot_cb.setToolTip(
            "Plot (show) this object."
        )
        grid0.addWidget(self.plot_cb, 0, 0)

        # Tool dia for plot
        tdlabel = QtGui.QLabel('Tool dia:')
        tdlabel.setToolTip(
            "Diameter of the tool to be\n"
            "rendered in the plot."
        )
        grid0.addWidget(tdlabel, 1, 0)
        self.tooldia_entry = LengthEntry()
        grid0.addWidget(self.tooldia_entry, 1, 1)

        ## Export G-Code
        self.export_gcode_label = QtGui.QLabel("<b>Export G-Code:</b>")
        self.export_gcode_label.setToolTip(
            "Export and save G-Code to\n"
            "make this object to a file."
        )
        self.layout.addWidget(self.export_gcode_label)

        # Append text to Gerber
        appendlabel = QtGui.QLabel('Append to G-Code:')
        appendlabel.setToolTip(
            "Type here any G-Code commands you would\n"
            "like to append to the generated file.\n"
            "I.e.: M2 (End of program)"
        )
        self.layout.addWidget(appendlabel)

        self.append_text = FCTextArea()
        self.layout.addWidget(self.append_text)


class GlobalOptionsUI(QtGui.QWidget):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent=parent)

        layout = QtGui.QVBoxLayout()
        self.setLayout(layout)

        hlay1 = QtGui.QHBoxLayout()
        layout.addLayout(hlay1)
        unitslabel = QtGui.QLabel('Units:')
        hlay1.addWidget(unitslabel)
        self.units_radio = RadioSet([{'label': 'inch', 'value': 'IN'},
                                     {'label': 'mm', 'value': 'MM'}])
        hlay1.addWidget(self.units_radio)

        ####### Gerber #######
        # gerberlabel = QtGui.QLabel('<b>Gerber Options</b>')
        # layout.addWidget(gerberlabel)
        self.gerber_group = GerberOptionsGroupUI()
        # self.gerber_group.setFrameStyle(QtGui.QFrame.StyledPanel)
        layout.addWidget(self.gerber_group)

        ####### Excellon #######
        # excellonlabel = QtGui.QLabel('<b>Excellon Options</b>')
        # layout.addWidget(excellonlabel)
        self.excellon_group = ExcellonOptionsGroupUI()
        # self.excellon_group.setFrameStyle(QtGui.QFrame.StyledPanel)
        layout.addWidget(self.excellon_group)

        ####### Geometry #######
        # geometrylabel = QtGui.QLabel('<b>Geometry Options</b>')
        # layout.addWidget(geometrylabel)
        self.geometry_group = GeometryOptionsGroupUI()
        # self.geometry_group.setStyle(QtGui.QFrame.StyledPanel)
        layout.addWidget(self.geometry_group)

        ####### CNC #######
        # cnclabel = QtGui.QLabel('<b>CNC Job Options</b>')
        # layout.addWidget(cnclabel)
        self.cncjob_group = CNCJobOptionsGroupUI()
        # self.cncjob_group.setStyle(QtGui.QFrame.StyledPanel)
        layout.addWidget(self.cncjob_group)

# def main():
#
#     app = QtGui.QApplication(sys.argv)
#     fc = FlatCAMGUI()
#     sys.exit(app.exec_())
#
#
# if __name__ == '__main__':
#     main()