import os, sys, numpy

from AnyQt.QtCore import Qt
from AnyQt.QtWidgets import QLabel, QApplication, QMessageBox, QSizePolicy
from AnyQt.QtGui import QTextCursor, QPixmap

import orangecanvas.resources as resources

from orangewidget import gui
from orangewidget.settings import Setting
from orangewidget.widget import Output

from oasys2.widget.widget import OWWidget, OWAction
from oasys2.widget import gui as oasysgui
from oasys2.widget.util import congruence
from oasys2.canvas.util.canvas_util import add_widget_parameters_to_module

from oasys2.widget.util.widget_util import EmittingStream
from orangecontrib.shadow4.util.shadow4_util import ShadowPhysics

from scipy.optimize import fsolve

#TODO: add output to connect directly to Shadow4 widgets, to use values on spherical grating and plane mirror


class OWVASGM(OWWidget):
    name = "VA-SGM Angles Calculator"
    id = "VASGMAnglesCalculator"
    description = "Calculation of angles for Variable-Angle SGM"
    icon = "icons/vasgm.png"
    author = "Juan Reyes Herrera"
    maintainer_email = "juan.reyesherrera@elettra.eu"
    priority = 100
    category = ""
    keywords = ["oasys", "vasgm", "angles", "calculator"]
    

    want_main_area = True
    

    r = Setting(10.0)
    rp = Setting(10.0)
    g_density = Setting(600e3)  # 600 lines/mm converted to lines/m
    radius = Setting(20.0)


    grating_diffraction_order = Setting(-1)

    

    units_in_use = Setting(0)
    photon_wavelength = Setting(25.0)
    photon_energy = Setting(500.0)
    #initial_guess_alpha_deg = Setting(57.0)
    #initial_guess_beta_deg = Setting(-57.0)

    #image_path = os.path.join(resources.package_dirname("orangecontrib.shadow4.widgets.gui"), "misc", "vls_pgm_layout.png")
    #usage_path = os.path.join(resources.package_dirname("orangecontrib.elettra.shadow4.widgets.extension"), "icons", "vasgm_usage.png")
    

    calc_alpha = Setting(0.0) #deg
    calc_beta = Setting(0.0) #deg

    estimated_included_angle = Setting(100.0) #deg

    plane_mirror_angle = Setting(0.0) #deg
    calc_included_angle = Setting(0.0) #deg

    shadow_g_diffraction_order = Setting(0) #deg

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

        tab_step_1 = oasysgui.createTabPage(tabs_setting, "VASGM Parameters")

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
                label.size()*.7, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            label.setPixmap(scaled_pixmap)
        else:
            label.setText("Image not found")
            label.setStyleSheet("color: red;")

        usage_box.layout().addWidget(label)

        box = oasysgui.widgetBox(tab_step_1, "Spherical Grating Parameters", orientation="vertical")

        oasysgui.lineEdit(box, self, "r", "Distance Source-Grating [m]", labelWidth=260, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(box, self, "rp", "Distance Grating-Image [m]", labelWidth=260, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(box, self, "g_density", "Grating Line Density [lines/m]", labelWidth=260, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(box, self, "radius", "Grating Radius [m]", labelWidth=260, valueType=float, orientation="horizontal")

        gui.separator(box)

        box_2 = oasysgui.widgetBox(tab_step_1, "SGM Parameters", orientation="vertical")
        

        gui.comboBox(box_2, self, "units_in_use", label="Units in use", labelWidth=260,
                     items=["eV", "Angstroms"],
                     callback=self.set_UnitsInUse, sendSelectedValue=False, orientation="horizontal")
        

        self.autosetting_box_units_1 = oasysgui.widgetBox(box_2, "", addSpace=False, orientation="vertical")

        oasysgui.lineEdit(self.autosetting_box_units_1, self, "photon_energy", "Photon energy [eV]", labelWidth=260, valueType=float, orientation="horizontal")

        self.autosetting_box_units_2 = oasysgui.widgetBox(box_2, "", addSpace=False, orientation="vertical")

        oasysgui.lineEdit(self.autosetting_box_units_2, self, "photon_wavelength", "Wavelength [Å]", labelWidth=260, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(box_2, self, "grating_diffraction_order", "Grating Diffraction Order", labelWidth=260, valueType=int, orientation="horizontal")
        oasysgui.lineEdit(box_2, self, "estimated_included_angle", "Estimated Included Angle [deg]", labelWidth=260, valueType=float, orientation="horizontal")
        #oasysgui.lineEdit(box_2, self, "initial_guess_alpha_deg", "Initial Guess Alpha [deg]", labelWidth=260, valueType=float, orientation="horizontal")
        #oasysgui.lineEdit(box_2, self, "initial_guess_beta_deg", "Initial Guess Beta [deg]", labelWidth=260, valueType=float, orientation="horizontal")

        self.set_UnitsInUse()

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

        oasysgui.lineEdit(output_box_1, self, "calc_alpha", "Alpha [deg]", labelWidth=220, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(output_box_1, self, "calc_beta", "Beta [deg] (use positive for shadow)", labelWidth=220, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(output_box_1, self, "plane_mirror_angle", "Plane Mirror Angle [deg]", labelWidth=220, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(output_box_1, self, "calc_included_angle", "Calculated Included Angle [deg]", labelWidth=220, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(output_box_1, self, "shadow_g_diffraction_order", "👁️ Shadow Grating Diffraction Order (- for inside orders)", labelWidth=320, valueType=int, orientation="horizontal")
        
        ## output tab ###
        self.shadow_output = oasysgui.textArea()

        out_box = oasysgui.widgetBox(tab_out_2, "System Output", addSpace=True, orientation="horizontal", height=400)
        out_box.layout().addWidget(self.shadow_output)

        gui.rubber(self.controlArea)

    def set_UnitsInUse(self):
        self.autosetting_box_units_1.setVisible(self.units_in_use == 0)
        self.autosetting_box_units_2.setVisible(self.units_in_use == 1)

    def solve_sgm_angles(cls,
                         r=0.0,
                         rp=0.0,
                         radius=0.0,
                         grating_diffraction_order=-1,
                         g_density=0.0,
                         photon_energy=0.0,                         
                         initial_guess=[0.0, 0.0],
                         verbose=0):
        """
        Solve for alpha and beta (incidence and diffraction angles) for a
        spherical grating monochromator.
    
        Parameters:
        -----------
        r : float
            Source-to-grating distance (in m)
        rp : float
            Grating-to-image (exit slit) distance (in m)
        radius : float
            Radius of curvature of the spherical grating (in m)
        g_density : float
            Groove density (lines per m)  (e.g., 600 lines/m)
        grating_diffraction_order : int
            Diffraction order (usually +1 or -1)
            notice that negative order are called outside orders,
             and positive orders are called inside orders.
        photon_energy : float
            Photon energy (in eV)
        angle_units : str
            'rad' for output in radians, 'deg' for output in degrees
        initial_guess : list
            Initial guess for [alpha, beta] in radians for the fsolve function
        verbose : bool
            If True, prints additional information during the solving process.
    
        Returns:
        --------
        alpha : float
            Incidence angle (degrees)
        beta : float
            Diffraction angle (degrees)
        """
        # Step 1: Groove spacing (m)
        d_m = 1.0 / g_density         
        wavelength = ShadowPhysics.getWavelengthFromEnergy(photon_energy) * 1e-10  # wavelength in meters

        if verbose:
            print("--- Solving for SGM Angles ---")
            print("Reference X-Ray Data Booklet, Malcolm R. Howells")
            print("https://xdb.lbl.gov/Section4/Sec_4-3Extended.pdf")
    
        def equations(vars):
            alpha, beta = vars
            eq1 = (numpy.cos(alpha)**2 / r - numpy.cos(alpha) / radius) + \
                  (numpy.cos(beta)**2 / rp - numpy.cos(beta) / radius)
            eq2 = numpy.sin(alpha) + numpy.sin(beta) - grating_diffraction_order * wavelength / d_m
            return [eq1, eq2]        
        
        alpha_rad, beta_rad = fsolve(equations, initial_guess)        
    
        calc_alpha = numpy.degrees(alpha_rad)
        calc_beta = numpy.degrees(beta_rad)
        plane_mirror_angle = (calc_alpha - calc_beta) / 2.0
        calc_included_angle = calc_alpha - calc_beta            
    
        if verbose:
            print(f"Photon energy: {photon_energy} eV")
            print(f"Wavelength: {wavelength:.3e} m")
            print(f"Groove spacing: {d_m:.3e} m")
            print(f"Alpha (incidence angle): {calc_alpha:.3f}")
            print(f"Beta (diffraction angle): {calc_beta:.3f}")
            print(f"Plane mirror angle: {plane_mirror_angle:.3f}°")
            print(f"Included angle (α - β): {calc_included_angle:.3f}°")
            print(f"Attention 👁️ Shadow Grating Diffraction Order (- for inside orders): {-1 *grating_diffraction_order}")
        
        return calc_alpha, calc_beta, plane_mirror_angle, calc_included_angle 

    def compute(self):

        try:
            self.shadow_output.setText("")

            sys.stdout = EmittingStream(textWritten=self.writeStdOut)

            self.checkFields()

            if self.units_in_use == 0:
                photon_energy = self.photon_energy
            elif self.units_in_use == 1:
                photon_energy = ShadowPhysics.getEnergyFromWavelength(self.photon_wavelength * 1e-10)  # Convert Å to m
            
            calc_alpha, calc_beta, plane_mirror_angle, calc_included_angle = \
                self.solve_sgm_angles(
                    r=self.r,
                    rp=self.rp,
                    radius=self.radius,
                    grating_diffraction_order=self.grating_diffraction_order,
                    g_density=self.g_density,
                    photon_energy=photon_energy,                         
                    initial_guess=[numpy.radians(self.estimated_included_angle/2), numpy.radians(-self.estimated_included_angle/2)],
                    verbose=1)
            
            self.calc_alpha          = numpy.round(calc_alpha, 3)
            self.calc_beta           = numpy.round(calc_beta, 3)
            self.plane_mirror_angle  = numpy.round(plane_mirror_angle, 3)
            self.calc_included_angle = numpy.round(calc_included_angle, 3)
            self.shadow_g_diffraction_order = -1 * self.grating_diffraction_order

        except Exception as exception:
            QMessageBox.critical(self, "Error", str(exception), QMessageBox.Ok)
            if self.IS_DEVELOP: raise exception

    def checkFields(self):
        self.r = congruence.checkStrictlyPositiveNumber(self.r, "Distance Source-Grating")
        self.rp = congruence.checkStrictlyPositiveNumber(self.rp, "Distance Grating-Exit Slits")        
        self.g_density = congruence.checkStrictlyPositiveNumber(self.g_density, "Grating Line Density [lines/m]")
        self.radius = congruence.checkStrictlyPositiveNumber(self.radius, "Grating Radius [m]")
        self.estimated_included_angle = congruence.checkStrictlyPositiveNumber(self.estimated_included_angle, "Estimated Included Angle [deg]")

        if self.units_in_use == 0:
            self.photon_energy = congruence.checkPositiveNumber(self.photon_energy, "Photon Energy")
        elif self.units_in_use == 1:
            self.photon_wavelength = congruence.checkPositiveNumber(self.photon_wavelength, "Photon Wavelength")
    
    def get_about_path(self):
        # Get the directory of the current file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, "images", "vasgm_about.png")

    def defaults(self):
         self._reset_settings()

    def writeStdOut(self, text):
        cursor = self.shadow_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.shadow_output.setTextCursor(cursor)
        self.shadow_output.ensureCursorVisible()

add_widget_parameters_to_module(__name__)

if __name__ == "__main__":
    
    from AnyQt.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    ow = OWVASGM()
    ow.r = 2.572
    ow.rp = 1.05
    ow.g_density = 1200000
    ow.radius = 32.49
    ow.photon_energy = 900.0
    ow.grating_diffraction_order = -1
    ow.estimated_included_angle = 174.0

    ow.show()
    app.exec()
    ow.saveSettings()