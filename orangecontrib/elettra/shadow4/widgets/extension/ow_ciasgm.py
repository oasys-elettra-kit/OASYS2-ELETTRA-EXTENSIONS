from AnyQt.QtCore import Qt
from AnyQt.QtWidgets import QLabel, QApplication, QMessageBox, QSizePolicy
from AnyQt.QtGui import QTextCursor, QPixmap

from orangewidget import gui
from orangewidget.settings import Setting
from orangewidget.widget import Output

from oasys2.widget.widget import OWWidget, OWAction
from oasys2.widget import gui as oasysgui
from oasys2.widget.util import congruence
from oasys2.canvas.util.canvas_util import add_widget_parameters_to_module

from oasys2.widget.util.widget_util import EmittingStream
from orangecontrib.shadow4.util.shadow4_util import ShadowPhysics

import numpy as np
import os, sys

class OWCIASGM(OWWidget):
    name = "CIA-SGM Calculator"
    id = "Calculator"
    description = "Calculation of angles for a spherical grating monochromator with constant included angle"
    icon = "icons/ciasgm.png"
    author = "Roberta Totani"
    maintainer_email = "roberta.totani@elettra.eu"
    priority = 101 
    category = ""
    keywords = ["oasys", "ciasgm", "angles", "calculator"]

    want_main_area = True
   
    g_density = Setting(1500e3)  # 1500 lines/mm converted to lines/m
    radius = Setting(5.0)

    grating_diffraction_order = Setting(1)    

    units_in_use = Setting(0)
    photon_wavelength = Setting(2.0)
    photon_energy = Setting(10.0)
    pH = Setting(0.0) #meters
    pV = Setting(0.0) #meters
    included_angle = Setting(5.0) #deg

    alpha_deg = Setting(0.0) #deg
    beta_deg = Setting(0.0) #deg    
    qH = Setting(0.0) #meters
    qV = Setting(0.0) #meters
 
    shadow_g_diffraction_order = Setting(0)


    def __init__(self):

        super().__init__()

        self.runaction = OWAction("Compute", self)
        self.runaction.triggered.connect(self.compute)
        self.addAction(self.runaction)

        self.setFixedWidth(1170)
        self.setFixedHeight(550)

        gui.separator(self.controlArea)

        box0 = oasysgui.widgetBox(self.controlArea, "", orientation="horizontal")

        #widget buttons: compute, set defaults, help
        button = gui.button(box0, self, "Compute", callback=self.compute)
        button.setFixedHeight(45)
        button = gui.button(box0, self, "Defaults", callback=self.defaults)
        button.setFixedHeight(45)

        tabs_setting = oasysgui.tabWidget(self.controlArea)
        tabs_setting.setFixedHeight(425)

        tab_step_1 = oasysgui.createTabPage(tabs_setting, "Spherical Grating Parameters")

        tab_about = oasysgui.createTabPage(tabs_setting, "About this Widget")
        tab_about.setStyleSheet("background-color: white;")

        usage_box = oasysgui.widgetBox(tab_about, "", addSpace=True, orientation="horizontal")

        label = QLabel("")
        label.setAlignment(Qt.AlignCenter)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Load and scale the pixmap
        pixmap = QPixmap(self.get_about_path())
        if not pixmap.isNull():
            # Scale to fit the label while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(
                label.size()*.8, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            label.setPixmap(scaled_pixmap)
        else:
            label.setText("Image not found")
            label.setStyleSheet("color: red;")

        usage_box.layout().addWidget(label)

        box = oasysgui.widgetBox(tab_step_1, "Spherical Grating Parameters", orientation="vertical")

        oasysgui.lineEdit(box, self, "g_density", "Grating Line Density [lines/m]", labelWidth=260, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(box, self, "radius", "Grating Radius [m]", labelWidth=260, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(box, self, "pH", "HOR Distance Source - Grating [m]", labelWidth=260, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(box, self, "pV", "VER Distance Source - Grating [m]", labelWidth=260, valueType=float, orientation="horizontal")
        

        gui.separator(box)

        box_2 = oasysgui.widgetBox(tab_step_1, "SGM Parameters", orientation="vertical")        

        gui.comboBox(box_2, self, "units_in_use", label="Units in use", labelWidth=260,
                     items=["eV", "Angstroms"],
                     callback=self.set_UnitsInUse, sendSelectedValue=False, orientation="horizontal")        

        self.autosetting_box_units_1 = oasysgui.widgetBox(box_2, "", addSpace=False, orientation="vertical")
        oasysgui.lineEdit(self.autosetting_box_units_1, self, "photon_energy", "Photon energy [eV]", labelWidth=260, valueType=float, orientation="horizontal")

        self.autosetting_box_units_2 = oasysgui.widgetBox(box_2, "", addSpace=False, orientation="vertical")
        oasysgui.lineEdit(self.autosetting_box_units_2, self, "photon_wavelength", "Wavelength [Å]", labelWidth=260, valueType=float, orientation="horizontal")

        self.set_UnitsInUse()

        oasysgui.lineEdit(box_2, self, "grating_diffraction_order", "Grating Diffraction Order", labelWidth=260, valueType=int, orientation="horizontal")
        oasysgui.lineEdit(box_2, self, "included_angle", "Grating Included Angle [deg]", labelWidth=260, valueType=int, orientation="horizontal")


        #### results tab #####
        tabs_out = oasysgui.tabWidget(self.mainArea)

        tab_out_1 = oasysgui.createTabPage(tabs_out, "Calculation Results")
        tab_out_2 = oasysgui.createTabPage(tabs_out, "Output")

        figure_box_1 = oasysgui.widgetBox(tab_out_1, "", addSpace=True, orientation="horizontal")

        #label = QLabel("")
        #label.setPixmap(QPixmap(self.image_path))

        #figure_box_1.layout().addWidget(label)

        output_box = oasysgui.widgetBox(tab_out_1, "", addSpace=True, orientation="horizontal")
        output_box_1 = oasysgui.widgetBox(output_box, "Calculations Output", addSpace=True, orientation="vertical")

        oasysgui.lineEdit(output_box_1, self, "alpha_deg", "Alpha [deg]", labelWidth=220, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(output_box_1, self, "beta_deg", "Beta [deg] (use positive for shadow)", labelWidth=220, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(output_box_1, self, "qH", "HOR Distance Grating - Image [m]", labelWidth=220, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(output_box_1, self, "qV", "VER Distance Grating - Image [m]", labelWidth=220, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(output_box_1, self, "included_angle", "Grating Included Angle [deg]", labelWidth=220, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(output_box_1, self, "shadow_g_diffraction_order", "👁️ Shadow Grating Diffraction Order (- for inside orders)", labelWidth=320, valueType=int, orientation="horizontal")
        
        ## output tab ###
        self.shadow_output = oasysgui.textArea()

        out_box = oasysgui.widgetBox(tab_out_2, "System Output", addSpace=True, orientation="horizontal", height=400)
        out_box.layout().addWidget(self.shadow_output)

        gui.rubber(self.controlArea)

    def set_UnitsInUse(self):

        self.autosetting_box_units_1.setVisible(self.units_in_use == 0)
        self.autosetting_box_units_2.setVisible(self.units_in_use == 1)

    @classmethod

    def solve_ciasgm(cls,
                         included_angle=0.0,
                         grating_diffraction_order=-1,
                         g_density=0.0,
                         radius = 0.0,
                         photon_energy=0.0,
                         pH=0.0,
                         pV=0.0,
                         verbose=0):
        """ 
        Solve for alpha and beta (incidence and diffraction angles) for a
        spherical grating monochromator with constant included angle (Rowland circle conditions).
    
        Parameters:
        -----------
        g_density : float
            Groove density (lines per m)  (e.g., 600 lines/m)
        radius = grating radius of curvature (m)
        grating_diffraction_order : int
            Diffraction order (usually +1 or -1)
            notice that negative order are called outside orders,
             and positive orders are called inside orders.
        included angle (with respect to the grating normal)
        photon_energy : float
            Photon energy (in eV)
        pH : distance Source - Grating in the horizontal direction (m)
        pV : distance Source - Grating in the vertical direction (m)
        angle_units : str
            'rad' for output in radians, 'deg' for output in degrees
        verbose : bool
            If True, prints additional information during the solving process.
    
        Returns:
        --------
        alpha : float
            Incidence angle (degrees)
        beta : float
            Diffraction angle (degrees)
        N.B. alpha and beta are defined with respect to the grating surface normal
        qH : distance grating - Image, in the horizontal direction
        qV : distance grating - Image, in the vertical direction
        """


        # Step 1: Groove spacing (m)
        #d_m = 1.0 / g_density         
        wavelength = ShadowPhysics.getWavelengthFromEnergy(photon_energy) * 1e-10  # wavelength in meters

        #Step 2: Included angle (rad)
        theta = np.deg2rad(included_angle)

        if verbose:
            print("--- Solving for Constant Included Angle SGM ---")
            print("Reference X-Ray Data Booklet, Malcolm R. Howells")
            print("https://xdb.lbl.gov/Section4/Sec_4-3Extended.pdf")

        # Step 3: evaluating alpha, beta = angles of incidence and diffraction, respectively, with a constant included angle configuration
        # alpha and beta are considered with respect to the surface normal

        beta_rad = np.asin(wavelength * g_density / (2 * np.cos(0.5 * theta))) - 0.5 * theta
        beta_deg = np.rad2deg(beta_rad)
        alpha_rad = theta + beta_rad
        alpha_deg = np.rad2deg(alpha_rad)
       
        #Step 4: evaluating now qH and qV, from the conditions F200 = 0 and F020 = 0
        
        qH = ((np.cos(alpha_rad) + np.cos(beta_rad)) / radius - 1 / pH) ** (-1)
        qV = (np.cos(beta_rad)) ** 2 / (
                (np.cos(alpha_rad) + np.cos(beta_rad)) / radius - (np.cos(alpha_rad)) ** 2 / pV)

        if verbose:
            print(f"Photon energy: {photon_energy} eV")
            print(f"Wavelength: {wavelength:.3e} m")
            print(f"Groove spacing: {g_density} lines/m")
            print(f"Included angle (α - β): {included_angle:.3f}°")
            print(f"Attention 👁️ Shadow Grating Diffraction Order (- for inside orders): {-1 *grating_diffraction_order}")
            print(f"Alpha (incidence angle): {alpha_deg:.3f}")
            print(f"Beta (diffraction angle): {beta_deg:.3f}")
            print(f"Distance Grating - Image HOR, i.e grating HOR focus position: {qH:.3f}")
            print(f"Distance Grating - Image VER, i.e. grating VER focus position: {qV:.3f}")

        return(alpha_deg, beta_deg, qH, qV)


    def compute(self):
        #pass
        try:
            self.shadow_output.setText("")

            sys.stdout = EmittingStream(textWritten=self.writeStdOut)

            self.checkFields()

            if self.units_in_use == 0:
                photon_energy = self.photon_energy
            elif self.units_in_use == 1:
                photon_energy = ShadowPhysics.getEnergyFromWavelength(self.photon_wavelength)  # Convert Å to m

            
            alpha_deg, beta_deg, qH, qV = \
                self.solve_ciasgm(
                included_angle=self.included_angle,
                         grating_diffraction_order=self.grating_diffraction_order,
                         g_density=self.g_density,
                         radius=self.radius,
                         photon_energy=photon_energy,
                         pH=self.pH,
                         pV=self.pV,
                         verbose=1)
            
            self.alpha_deg          = np.round(alpha_deg, 3)
            self.beta_deg           = np.round(beta_deg, 3)
            self.qH                 = np.round(qH, 3)
            self.qV                 = np.round(qV, 3)
            self.shadow_g_diffraction_order = -1 * self.grating_diffraction_order


        except Exception as exception:
            QMessageBox.critical(self, "Error", str(exception), QMessageBox.Ok)
            if self.IS_DEVELOP: raise exception

    def checkFields(self):  
        self.g_density = congruence.checkStrictlyPositiveNumber(self.g_density, "Grating Line Density [lines/m]")       
        self.grating_diffraction_order = congruence.checkNumber(self.grating_diffraction_order, "Grating Diffraction Order")
        self.pH = congruence.checkStrictlyPositiveNumber(self.pH, "Distance Source - Grating [m] HOR")
        self.pV = congruence.checkStrictlyPositiveNumber(self.pV, "Distance Source - Grating VER [m]")
        if self.units_in_use == 0:
            self.photon_energy = congruence.checkPositiveNumber(self.photon_energy, "Photon Energy")
        elif self.units_in_use == 1:
            self.photon_wavelength = congruence.checkPositiveNumber(self.photon_wavelength, "Photon Wavelength") 


    def get_about_path(self):
        # Get the directory of the current file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, "images", "ciasgm_about.png")

    def defaults(self):
        self._reset_settings()

    def writeStdOut(self, text):
        cursor = self.shadow_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.shadow_output.setTextCursor(cursor)
        self.shadow_output.ensureCursorVisible()


add_widget_parameters_to_module(__name__)

"""This part of the code is for testing the widget independently.
    It creates a QApplication, initializes the OWCIASGM widget,
    sets some default parameters, and displays the widget.
    After the application event loop ends, it saves the widget settings."""

if __name__ == "__main__":
    
    from AnyQt.QtWidgets import QApplication
    import sys

    
    app = QApplication(sys.argv)
    ow = OWCIASGM()
    ow.pH = 3.83
    ow.pV = 3.834
    ow.rp = 4.237
    ow.g_density = 1500000
    ow.radius = 4.038
    ow.photon_energy = 6.4
    ow.grating_diffraction_order = 1
    ow.included_angle = 5

    ow.show()
    app.exec()
    ow.saveSettings()