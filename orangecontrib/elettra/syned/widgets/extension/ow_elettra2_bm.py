import os, sys
import numpy
import pandas
import scipy.constants as codata


from syned.storage_ring.magnetic_structures.bending_magnet import BendingMagnet

from AnyQt.QtGui import QPalette, QColor, QFont
from AnyQt.QtWidgets import QMessageBox, QApplication
from AnyQt.QtCore import QRect

from AnyQt.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QScrollArea, QWidget
)
from AnyQt.QtGui import QPixmap
from AnyQt.QtCore import Qt

from orangewidget import gui

from orangewidget.settings import Setting

from oasys2.widget.widget import OWWidget, OWAction
from oasys2.widget import gui as oasysgui
from oasys2.widget.util import congruence

from syned.storage_ring.light_source import LightSource, ElectronBeam
from syned.beamline.beamline import Beamline

from oasys2.widget.gui import ConfirmDialog

import orangecanvas.resources as resources

from syned.util.json_tools import load_from_json_file

from orangewidget.widget import Output
from oasys2.canvas.util.canvas_util import add_widget_parameters_to_module

m2ev = codata.c * codata.h / codata.e

VERTICAL = 1
HORIZONTAL = 2
BOTH = 3


class OWELETTRA2BM(OWWidget):

    name = "Elettra BM Sources"
    description = "Syned: Elettra 2.0 BM Light Source"
    icon = "icons/bm_source_elettra.png"
    priority = 2.1


    maintainer = "Juan Reyes Herrera"
    maintainer_email = "juan.reyesherrera(@at@)elettra.eu"
    category = "Elettra2 Syned Light Sources"
    keywords = ["data", "file", "load", "read"]

    class Outputs:
        SynedData = Output("SynedData", Beamline)

    want_main_area = 1


    MAX_WIDTH = 1320
    MAX_HEIGHT = 720

    IMAGE_WIDTH = 860
    IMAGE_HEIGHT = 645

    CONTROL_AREA_WIDTH = 405
    TABS_AREA_HEIGHT = 680

    #TABS_AREA_HEIGHT = 625
    #CONTROL_AREA_WIDTH = 450


    electron_energy_in_GeV = Setting(2.4)
    electron_energy_spread = Setting(0.000934)
    ring_current           = Setting(0.4)
    number_of_bunches      = Setting(0.0)

    use_dispersion = Setting(1) # 0 no, 1 yes

    moment_xx           = Setting(0.0)
    moment_xxp          = Setting(0.0)
    moment_xpxp         = Setting(0.0)
    moment_yy           = Setting(0.0)
    moment_yyp          = Setting(0.0)
    moment_ypyp         = Setting(0.0)

    electron_beam_size_h       = Setting(0.0)
    electron_beam_divergence_h = Setting(0.0)
    electron_beam_size_v       = Setting(0.0)
    electron_beam_divergence_v = Setting(0.0)

    electron_beam_emittance_h = Setting(0.0)
    electron_beam_emittance_v = Setting(0.0)
    electron_beam_beta_h = Setting(0.0)
    electron_beam_beta_v = Setting(0.0)
    electron_beam_alpha_h = Setting(0.0)
    electron_beam_alpha_v = Setting(0.0)
    electron_beam_eta_h = Setting(0.0)
    electron_beam_eta_v = Setting(0.0)
    electron_beam_etap_h = Setting(0.0)
    electron_beam_etap_v = Setting(0.0)

    type_of_properties = Setting(1)
    type_of_properties_initial_selection = type_of_properties
    
    radius         = Setting(5.48)
    magnetic_field = Setting(1.46)
    length         = Setting(0.22)    

    elettra_bl_index = Setting(0)     
    
    # pow_dens_screen = Setting(30.0)
    
    data_url = os.path.join(resources.package_dirname("orangecontrib.elettra.syned.data"), 'elettra2_bm_sources.csv')
    #data_e_bm = os.path.join(resources.package_dirname("orangecontrib.elettra.syned.data"), 'Elettra_Long_Straight.json')
    
    data_dict = None

    def __init__(self):

        self.get_data_dictionary_csv() #reads the CSV file with the sources info
        #self.get_bm_electronbeam() #reads long section e-beam parameters JSON
        
        self.runaction = OWAction("Send Data", self)
        self.runaction.triggered.connect(self.send_data)
        self.addAction(self.runaction)

        button_box = oasysgui.widgetBox(self.controlArea, "", addSpace=False, orientation="horizontal")

        button = gui.button(button_box, self, "Send Data", callback=self.send_data)
        font = QFont(button.font())
        font.setBold(True)
        button.setFont(font)
        palette = QPalette(button.palette()) # make a copy of the palette
        palette.setColor(QPalette.ButtonText, QColor('Dark Blue'))
        button.setPalette(palette) # assign new palette
        button.setFixedHeight(45)

        button = gui.button(button_box, self, "About", callback=self.show_about)
        font = QFont(button.font())
        font.setItalic(True)
        button.setFont(font)
        palette = QPalette(button.palette()) # make a copy of the palette
        palette.setColor(QPalette.ButtonText, QColor('Dark Red'))
        button.setPalette(palette) # assign new palette
        button.setFixedHeight(45)
        button.setFixedWidth(150)

        gui.separator(self.controlArea)

        geom = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(QRect(round(geom.width() * 0.05),
                               round(geom.height() * 0.05),
                               round(min(geom.width() * 0.98, self.MAX_WIDTH)),
                               round(min(geom.height() * 0.95, self.MAX_HEIGHT))))

        self.setMaximumHeight(self.geometry().height())
        self.setMaximumWidth(self.geometry().width())

        self.controlArea.setFixedWidth(self.CONTROL_AREA_WIDTH)

        self.tabs_setting = oasysgui.tabWidget(self.controlArea)
        self.tabs_setting.setFixedHeight(self.TABS_AREA_HEIGHT)
        self.tabs_setting.setFixedWidth(self.CONTROL_AREA_WIDTH - 5)

        self.tab_sou = oasysgui.createTabPage(self.tabs_setting, "Light Source Setting")

        gui.comboBox(self.tab_sou, self, "elettra_bl_index", label="Load BM parameters from Beamline name: ", labelWidth=350,
                     items=self.get_bl_list(), callback=self.set_bl, sendSelectedValue=False, orientation="horizontal")
        

        self.electron_beam_box = oasysgui.widgetBox(self.tab_sou, "Electron Beam/Machine Parameters", addSpace=False, orientation="vertical")

        oasysgui.lineEdit(self.electron_beam_box, self, "electron_energy_in_GeV", "Energy [GeV]",  labelWidth=260, valueType=float, orientation="horizontal", callback=self.update)
        oasysgui.lineEdit(self.electron_beam_box, self, "electron_energy_spread", "Energy Spread", labelWidth=260, valueType=float, orientation="horizontal", callback=self.update)
        oasysgui.lineEdit(self.electron_beam_box, self, "ring_current", "Ring Current [A]",        labelWidth=260, valueType=float, orientation="horizontal", callback=self.update)

        gui.comboBox(self.electron_beam_box, self, "type_of_properties", label="Electron Beam Properties", labelWidth=350,
                     items=["From 2nd Moments", "From Size/Divergence", "From Twiss papameters","Zero emittance"],
                     callback=self.update_electron_beam,
                     sendSelectedValue=False, orientation="horizontal")
        #box = gui.widgetBox(self.controlArea, "Options")
        gui.comboBox(self.electron_beam_box, self, "use_dispersion", label="Use Dispersion in Size/Divergence and Moments calculations", labelWidth=350,
                     items=["No","Yes"],
                     callback=self.set_use_dispersion,
                     sendSelectedValue=False, orientation="horizontal")


        self.left_box_2_1 = oasysgui.widgetBox(self.electron_beam_box, "", addSpace=False, orientation="horizontal", height=185)

        self.left_box_2_1_l = oasysgui.widgetBox(self.left_box_2_1, "", addSpace=False, orientation="vertical")
        self.left_box_2_1_r = oasysgui.widgetBox(self.left_box_2_1, "", addSpace=False, orientation="vertical")

        oasysgui.lineEdit(self.left_box_2_1_l, self, "moment_xx",   "<xx>[m^2]",    labelWidth=70, valueType=float, orientation="horizontal",  callback=self.update)
        oasysgui.lineEdit(self.left_box_2_1_l, self, "moment_xxp",  "<xx'>[m.rad]", labelWidth=70, valueType=float, orientation="horizontal",  callback=self.update)
        oasysgui.lineEdit(self.left_box_2_1_l, self, "moment_xpxp", "<x'x'>[rad^2]",labelWidth=70, valueType=float, orientation="horizontal",  callback=self.update)

        oasysgui.lineEdit(self.left_box_2_1_r, self, "moment_yy",   "<yy>[m^2]",    labelWidth=70, valueType=float, orientation="horizontal",  callback=self.update)
        oasysgui.lineEdit(self.left_box_2_1_r, self, "moment_yyp",  "<yy'>[m.rad]", labelWidth=70, valueType=float, orientation="horizontal",  callback=self.update)
        oasysgui.lineEdit(self.left_box_2_1_r, self, "moment_ypyp", "<y'y'>[rad^2]",labelWidth=70, valueType=float, orientation="horizontal",  callback=self.update)


        self.left_box_2_2 = oasysgui.widgetBox(self.electron_beam_box, "", addSpace=False, orientation="vertical", height=150)

        oasysgui.lineEdit(self.left_box_2_2, self, "electron_beam_size_h",       "Horizontal Beam Size \u03c3x [m]",          labelWidth=260, valueType=float, orientation="horizontal",  callback=self.update)
        oasysgui.lineEdit(self.left_box_2_2, self, "electron_beam_size_v",       "Vertical Beam Size \u03c3y [m]",            labelWidth=260, valueType=float, orientation="horizontal",  callback=self.update)
        oasysgui.lineEdit(self.left_box_2_2, self, "electron_beam_divergence_h", "Horizontal Beam Divergence \u03c3'x [rad]", labelWidth=260, valueType=float, orientation="horizontal",  callback=self.update)
        oasysgui.lineEdit(self.left_box_2_2, self, "electron_beam_divergence_v", "Vertical Beam Divergence \u03c3'y [rad]",   labelWidth=260, valueType=float, orientation="horizontal",  callback=self.update)

        self.left_box_2_3 = oasysgui.widgetBox(self.electron_beam_box, "", addSpace=False, orientation="horizontal",height=150)
        self.left_box_2_3_l = oasysgui.widgetBox(self.left_box_2_3, "", addSpace=False, orientation="vertical")
        self.left_box_2_3_r = oasysgui.widgetBox(self.left_box_2_3, "", addSpace=False, orientation="vertical")
        oasysgui.lineEdit(self.left_box_2_3_l, self, "electron_beam_emittance_h", "\u03B5x [m.rad]",labelWidth=75, valueType=float, orientation="horizontal",  callback=self.update)
        oasysgui.lineEdit(self.left_box_2_3_l, self, "electron_beam_alpha_h",     "\u03B1x",        labelWidth=75, valueType=float, orientation="horizontal",  callback=self.update)
        oasysgui.lineEdit(self.left_box_2_3_l, self, "electron_beam_beta_h",      "\u03B2x [m]",    labelWidth=75, valueType=float, orientation="horizontal",  callback=self.update)
        oasysgui.lineEdit(self.left_box_2_3_l, self, "electron_beam_eta_h",       "\u03B7x",        labelWidth=75, valueType=float, orientation="horizontal",  callback=self.update)
        oasysgui.lineEdit(self.left_box_2_3_l, self, "electron_beam_etap_h",      "\u03B7'x",       labelWidth=75, valueType=float, orientation="horizontal",  callback=self.update)


        oasysgui.lineEdit(self.left_box_2_3_r, self, "electron_beam_emittance_v", "\u03B5y [m.rad]",labelWidth=75, valueType=float, orientation="horizontal",  callback=self.update)
        oasysgui.lineEdit(self.left_box_2_3_r, self, "electron_beam_alpha_v",     "\u03B1y",        labelWidth=75, valueType=float, orientation="horizontal",  callback=self.update)
        oasysgui.lineEdit(self.left_box_2_3_r, self, "electron_beam_beta_v",      "\u03B2y [m]",    labelWidth=75, valueType=float, orientation="horizontal",  callback=self.update)
        oasysgui.lineEdit(self.left_box_2_3_r, self, "electron_beam_eta_v",       "\u03B7y",        labelWidth=75, valueType=float, orientation="horizontal",  callback=self.update)
        oasysgui.lineEdit(self.left_box_2_3_r, self, "electron_beam_etap_v",      "\u03B7'y",       labelWidth=75, valueType=float, orientation="horizontal",  callback=self.update)

        gui.rubber(self.controlArea)

        ###################

        left_box_1 = oasysgui.widgetBox(self.tab_sou, "BM Parameters", addSpace=False, orientation="vertical")

        oasysgui.lineEdit(left_box_1, self, "radius", "Magnetic Radius [m]", labelWidth=200,
                          valueType=float, orientation="horizontal", callback=self.calculateMagneticField)
        oasysgui.lineEdit(left_box_1, self, "magnetic_field", "Magnetic Field [T]", labelWidth=200,
                          valueType=float, orientation="horizontal", callback=self.calculateMagneticRadius)
        oasysgui.lineEdit(left_box_1, self, "length", "Length [m]", labelWidth=200,
                                  valueType=float, orientation="horizontal", callback=self.update)

        self.initializeTabs()
        self.populate_electron_beam()
        self.set_visible()
        self.update()

    def get_bl_list(self):
        out_list = [self.data_dict["beamline_name"][i] for i in
                   range(len(self.data_dict["beamline_name"]))]

        out_list.insert(0,"<None>") # We add None at the beginning: elettra_bl_name is the dict index plus one
        return out_list
    
    def get_bm_list(self):
            out_list = [self.data_dict["bm_name"][i] for i in
                       range(len(self.data_dict["bm_name"]))]
    
            out_list.insert(0,"<None>") # We add None at the beginning: elettra_id_name is the dict index plus one
            return out_list    


    def initializeTabs(self):
        self.tabs = oasysgui.tabWidget(self.mainArea)

        self.tab = [oasysgui.createTabPage(self.tabs, "Info",),
                    ]

        for tab in self.tab:
            tab.setFixedHeight(self.IMAGE_HEIGHT)
            tab.setFixedWidth(self.IMAGE_WIDTH)


        self.info_id = oasysgui.textArea(height=self.IMAGE_HEIGHT-5, width=self.IMAGE_WIDTH-5)
        profile_box = oasysgui.widgetBox(self.tab[0], "", addSpace=True, orientation="horizontal",
                                         height = self.IMAGE_HEIGHT, width=self.IMAGE_WIDTH-5)
        profile_box.layout().addWidget(self.info_id)

        self.tabs.setCurrentIndex(1)

    def check_magnetic_structure(self):
        congruence.checkPositiveNumber(self.radius, "Magnetic Radius [m]")
        congruence.checkPositiveNumber(self.magnetic_field, "Magnetic Field [T]")        
        congruence.checkStrictlyPositiveNumber(self.length, "Length [m]")
        

    def set_use_dispersion(self):
        if self.use_dispersion == 0:
            self.use_dispersion = False
        else:
            self.use_dispersion = True
        self.update()
        self.set_id()

    def set_electron_beam(self):
        
        # First we set the type of properties to 2, so that the values
        # are taken from the JSON

        self.type_of_properties = 2
        ex, ax, bx, ey, ay, by = self.electronbeam.get_twiss_all()
        nx, npx, ny, npy = self.electronbeam.get_dispersion_all()

        self.electron_beam_beta_h = bx
        self.electron_beam_beta_v = by
        self.electron_beam_alpha_h = ax
        self.electron_beam_alpha_v = ay
        self.electron_beam_eta_h = nx
        self.electron_beam_eta_v = ny
        self.electron_beam_etap_h = npx
        self.electron_beam_etap_v = npy
        self.electron_beam_emittance_h = ex
        self.electron_beam_emittance_v = ey

        # Now we calculate the size and divergence from the Twiss parameters
        # including dispersion

        eb = self.get_electron_beam()

        x, xp, y, yp = eb.get_sigmas_all(dispersion=self.use_dispersion)
        self.electron_beam_size_h =       numpy.round(x,12)
        self.electron_beam_size_v =       numpy.round(y,12)
        self.electron_beam_divergence_h = numpy.round(xp,12)
        self.electron_beam_divergence_v = numpy.round(yp,12)

        # Here we calculate the 2nd moments from the Twiss parameters
        # including dispersion

        moment_xx, moment_xxp, moment_xpxp, moment_yy, moment_yyp, moment_ypyp = eb.get_moments_all(dispersion=self.use_dispersion)
        self.moment_xx   = moment_xx
        self.moment_yy   = moment_yy
        self.moment_xxp  = moment_xxp
        self.moment_yyp  = moment_yyp
        self.moment_xpxp = moment_xpxp
        self.moment_ypyp = moment_ypyp

        # in order to keep the tag of properties selection

        if self.type_of_properties_initial_selection < 4:
            self.type_of_properties = self.type_of_properties_initial_selection
   

    def get_bl_number(self):
        if self.elettra_bl_index == 0: # <None>
            bl = 1 # this is by convention, zero would give errors
        else:
            label = self.get_bl_list()[self.elettra_bl_index]
            bl= int(label[2:4])
        return bl


    def update_electron_beam(self):

        if self.elettra_bl_index!=0:

            self.type_of_properties_initial_selection = self.type_of_properties
    
            self.set_electron_beam()
            self.set_visible()
            self.update()
        else:
            self.type_of_properties_initial_selection = self.type_of_properties

    def update(self):
        #pass
        self.check_data()
        self.update_info()        

    def update_info(self):

        syned_electron_beam = self.get_electron_beam()
        syned_bending_magnet = self.get_magnetic_structure()

        gamma = self.gamma()

        if self.elettra_bl_index == 0:            
            elettra_beamline = "<None>"
            bm_name = "<None>"
            position = "<None>"            

        else:
            try:                
                elettra_beamline = self.data_dict["beamline_name"][self.elettra_bl_index-1]
                bm_name = self.data_dict["bm_name"][self.elettra_bl_index-1]
                position = self.data_dict["position"][self.elettra_bl_index-1]
                
            except Exception as e:
                # If settings loading fails, reinitialize to defaults
                #self._handle_settings_load_failure(e)
                print("Error getting BM information from data dictionary:", e)
                print("Setting all BM information to <None>")                
                elettra_beamline = "<None>"
                bm_name = "<None>"
                position = "<None>"
                
                QMessageBox.critical(self, "Error", str(e)+"Sorry, something went wrong while setting BM information. All BM Elettra2.0 widget info has been set to <None>", QMessageBox.Ok)

        info_parameters = {
            "electron_energy_in_GeV":self.electron_energy_in_GeV,
            "gamma":"%8.3f"%self.gamma(),
            "ring_current":"%4.3f "%syned_electron_beam.current(),
            "magnetic_radius":syned_bending_magnet.radius(),
            "magnetic_field": syned_bending_magnet.magnetic_field(),
            "length": syned_bending_magnet.length(),         
            "horizontal_divergence": "%4.3f "%syned_bending_magnet.horizontal_divergence(),
            "critical_energy": "%4.3f "%syned_bending_magnet.calculate_critical_energy_from_magnetic_field(self.magnetic_field, self.electron_energy_in_GeV),            
            "url": self.data_url,            
            "beamline":elettra_beamline,
            "bm_name":bm_name,
            "position":position,      
            }

        self.info_id.setText(self.info_template().format_map(info_parameters))


    def info_template(self):
        return \
"""
data url: {url}
beamline: {beamline}
bm_name:  {bm_name}
position: {position}

================ input parameters ===========
Electron beam energy [GeV]: {electron_energy_in_GeV}
Electron current:           {ring_current}
Magnetic Radius [m]:        {magnetic_radius}
Magnetic Field [T]:         {magnetic_field}
Length [m]:                 {length}
==============================================

Electron beam gamma:        {gamma}
Horizontal divergence:      {horizontal_divergence}
Critical energy [eV]:       {critical_energy}

"""

    def get_magnetic_structure(self):

        return BendingMagnet(radius=self.radius,
                             magnetic_field=self.magnetic_field,
                             length=self.length)

    def check_magnetic_structure_instance(self, magnetic_structure):
        if not isinstance(magnetic_structure, BendingMagnet):
            raise ValueError("Magnetic Structure is not a Bending Magnet")

    def populate_magnetic_structure(self):
        # if magnetic_structure is None:
        if self.elettra_bl_index!=0:
                    file_url = os.path.join(resources.package_dirname("orangecontrib.elettra.syned.data"), self.data_dict["json_bm_file"][self.elettra_bl_index-1])
                    elettra_bm = load_from_json_file(file_url)
                    self.magnetic_structure = elettra_bm.get_magnetic_structure()
                    self.radius = self.magnetic_structure.radius()
                    self.magnetic_field =  self.magnetic_structure.magnetic_field()
                    self.length = self.magnetic_structure.length()        

    def set_bl(self):

        if self.elettra_bl_index!=0:
            self.get_bm_electronbeam()
            self.populate_magnetic_structure()
            self.update_electron_beam()
      
        self.update()            

    def calculateMagneticField(self):
        if self.radius > 0:
           self.magnetic_field=BendingMagnet.calculate_magnetic_field(self.radius, self.electron_energy_in_GeV)

    def calculateMagneticRadius(self):
        if self.magnetic_field > 0:
           self.radius=BendingMagnet.calculate_magnetic_radius(self.magnetic_field, self.electron_energy_in_GeV)   

    def gamma(self):
        return 1e9*self.electron_energy_in_GeV / (codata.m_e *  codata.c**2 / codata.e)

    def set_visible(self):
        self.left_box_2_1.setVisible(self.type_of_properties == 0)
        self.left_box_2_2.setVisible(self.type_of_properties == 1)
        self.left_box_2_3.setVisible(self.type_of_properties == 2)

    def check_data(self):
        congruence.checkStrictlyPositiveNumber(self.electron_energy_in_GeV , "Energy")
        congruence.checkStrictlyPositiveNumber(self.electron_energy_spread, "Energy Spread")
        congruence.checkStrictlyPositiveNumber(self.ring_current, "Ring Current")

        if self.type_of_properties == 0:
            congruence.checkPositiveNumber(self.moment_xx   , "Moment xx")
            congruence.checkPositiveNumber(self.moment_xpxp , "Moment xpxp")
            congruence.checkPositiveNumber(self.moment_yy   , "Moment yy")
            congruence.checkPositiveNumber(self.moment_ypyp , "Moment ypyp")
        elif self.type_of_properties == 1:
            congruence.checkPositiveNumber(self.electron_beam_size_h       , "Horizontal Beam Size")
            congruence.checkPositiveNumber(self.electron_beam_divergence_h , "Vertical Beam Size")
            congruence.checkPositiveNumber(self.electron_beam_size_v       , "Horizontal Beam Divergence")
            congruence.checkPositiveNumber(self.electron_beam_divergence_v , "Vertical Beam Divergence")
        elif self.type_of_properties == 2:
            congruence.checkPositiveNumber(self.electron_beam_emittance_h, "Horizontal Beam Emittance")
            congruence.checkPositiveNumber(self.electron_beam_emittance_v, "Vertical Beam Emittance")
            congruence.checkNumber(self.electron_beam_alpha_h, "Horizontal Beam Alpha")
            congruence.checkNumber(self.electron_beam_alpha_v, "Vertical Beam Alpha")
            congruence.checkNumber(self.electron_beam_beta_h, "Horizontal Beam Beta")
            congruence.checkNumber(self.electron_beam_beta_v, "Vertical Beam Beta")
            congruence.checkNumber(self.electron_beam_eta_h, "Horizontal Beam Dispersion Eta")
            congruence.checkNumber(self.electron_beam_eta_v, "Vertical Beam Dispersion Eta")
            congruence.checkNumber(self.electron_beam_etap_h, "Horizontal Beam Dispersion Eta'")
            congruence.checkNumber(self.electron_beam_etap_v, "Vertical Beam Dispersion Eta'")

        self.check_magnetic_structure()

    def send_data(self):
        self.update()
        try:
            self.check_data()
            self.Outputs.SynedData.send(Beamline(light_source=self.get_light_source()))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e.args[0]), QMessageBox.Ok)

            self.setStatusMessage("")
            self.progressBarFinished()

    def get_electron_beam(self):
        electron_beam = ElectronBeam(energy_in_GeV=self.electron_energy_in_GeV,
                                     energy_spread=self.electron_energy_spread,
                                     current=self.ring_current,
                                     number_of_bunches=self.number_of_bunches)

        if self.type_of_properties == 0:
            electron_beam.set_moments_horizontal(self.moment_xx,self.moment_xxp,self.moment_xpxp)
            electron_beam.set_moments_vertical(self.moment_yy, self.moment_yyp, self.moment_ypyp)

        elif self.type_of_properties == 1:
            electron_beam.set_sigmas_all(sigma_x=self.electron_beam_size_h,
                                         sigma_y=self.electron_beam_size_v,
                                         sigma_xp=self.electron_beam_divergence_h,
                                         sigma_yp=self.electron_beam_divergence_v)

        elif self.type_of_properties == 2:
            electron_beam.set_twiss_horizontal(self.electron_beam_emittance_h,
                                             self.electron_beam_alpha_h,
                                             self.electron_beam_beta_h)
            electron_beam.set_dispersion_horizontal(self.electron_beam_eta_h,
                                                   self.electron_beam_etap_h)
            electron_beam.set_twiss_vertical(self.electron_beam_emittance_v,
                                             self.electron_beam_alpha_v,
                                             self.electron_beam_beta_v)
            electron_beam.set_dispersion_vertical(self.electron_beam_eta_v,
                                                   self.electron_beam_etap_v)


        elif self.type_of_properties == 3:
            electron_beam.set_moments_all(0,0,0,0,0,0)

        return electron_beam

    def get_light_source(self):
        return LightSource(name=self.get_bm_list()[self.elettra_bl_index],
                           electron_beam = self.get_electron_beam(),
                           magnetic_structure = self.get_magnetic_structure())

    def callResetSettings(self):
        if ConfirmDialog.confirmed(parent=self, message="Confirm Reset of the Fields?"):
            try:
                self.resetSettings()
            except:
                pass

    def populate_electron_beam(self, electron_beam=None):
        if electron_beam is None:
            electron_beam = ElectronBeam(
                                        energy_in_GeV = 2.4,
                                        energy_spread = 0.000934,
                                        current = 0.4,
                                        number_of_bunches = 1,
                                        moment_xx   = (3.01836e-05)**2,
                                        moment_xxp  = (0.0)**2,
                                        moment_xpxp = (4.36821e-06)**2,
                                        moment_yy   = (3.63641e-06)**2,
                                        moment_yyp  = (0.0)**2,
                                        moment_ypyp = (1.37498e-06)**2,
                                        )

        self.electron_energy_in_GeV = electron_beam._energy_in_GeV
        self.electron_energy_spread = electron_beam._energy_spread
        self.ring_current = electron_beam._current
        self.number_of_bunches = electron_beam._number_of_bunches

        self.type_of_properties = 1

        self.moment_xx   = electron_beam._moment_xx
        self.moment_xxp  = electron_beam._moment_xxp
        self.moment_xpxp = electron_beam._moment_xpxp
        self.moment_yy   = electron_beam._moment_yy
        self.moment_yyp  = electron_beam._moment_yyp
        self.moment_ypyp = electron_beam._moment_ypyp

        x, xp, y, yp = electron_beam.get_sigmas_all()

        self.electron_beam_size_h = x
        self.electron_beam_size_v = y
        self.electron_beam_divergence_h = xp
        self.electron_beam_divergence_v = yp

    def get_data_dictionary_csv(self):
        """ Here we read the CSV file to get the different properties of each
        Elettra 2.0 bm source """       

        try:
        
            df = pandas.read_csv(self.data_url)
                       
            beamline_name = df['Beamline']
            bm_name = df['bm_name']
            position = df['Position']
            json_bm_file = df['json_bm_file']     
            out_dict = {}
            out_dict["beamline_name"] = beamline_name.to_list()
            out_dict["position"] = position.to_list()            
            out_dict["bm_name"] = bm_name.to_list()
            out_dict["json_bm_file"] = json_bm_file.to_list()
            

        except:
            print("Something went wrong while reading the file")
            out_dict = {}
            out_dict["beamline_name"] = []
            out_dict["position"] =      []
            out_dict["bm_name"] =       []
            out_dict["json_bm_file"] =  []            
        self.data_dict = out_dict

    # BM Electron parameters
    def get_bm_electronbeam(self):
        if self.elettra_bl_index!=0:
            file_url = os.path.join(resources.package_dirname("orangecontrib.elettra.syned.data"), self.data_dict["json_bm_file"][self.elettra_bl_index-1])
            elettra_bm = load_from_json_file(file_url)
            self.electronbeam = elettra_bm.get_electron_beam()   
    
    # -------------------------------------------------
    # Widget about info dialog with scrollable image
    # -------------------------------------------------
    def show_about(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Elettra2.0 Information")
        dlg.resize(700, 600)

        layout = QVBoxLayout(dlg)

        # Load image from installed package
        img_path = os.path.join(resources.package_dirname("orangecontrib.elettra.syned.data"), 'elettra2_bm_data.png')
        pixmap = QPixmap(img_path)

        if pixmap.isNull():
            label = QLabel("Info image not found.\nCheck package_data and MANIFEST.in")
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)
        else:
            # Container widget (important!)
            container = QWidget()
            container_layout = QVBoxLayout(container)

            image_label = QLabel()
            image_label.setPixmap(pixmap)
            image_label.setAlignment(Qt.AlignCenter)

            #Critical line: make label keep original image size
            image_label.setMinimumSize(pixmap.width(), pixmap.height())

            container_layout.addWidget(image_label)

            scroll = QScrollArea()
            scroll.setWidget(container)
            scroll.setWidgetResizable(False)  # Enables scrolling
            scroll.setAlignment(Qt.AlignCenter)

            layout.addWidget(scroll)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)
        # dlg.exec_() # This would make the dialog modal, but it frozen the main window until closed.
        # instead, we want a non-modal dialog:
        dlg.setModal(False)
        dlg.show()

add_widget_parameters_to_module(__name__)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ow = OWELETTRA2BM()
    ow.show()
    app.exec()
    ow.saveSettings()
    #pass