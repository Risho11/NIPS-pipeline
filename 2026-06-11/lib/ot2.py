# for opentrons code, present very simple interface only for sample crafting
import time
from opentrons import protocol_api
import opentrons.execute
import numpy as np
#import opentrons.simulate
import calculations as calc

polymer_stock_wt_percent = 21
additive_stock_additive_wt_percent = 4
additive_stock_polymer_wt_percent = 21

solution_slot_no = 9
solution_well_no = 0
solvent_slot_no = 6
solvent_well_no = 0
heater_slot_no = 11
additive_1_slot_no = 9
additive_1_well_no = 1

dict_labware = {
                1: 'amlab_cast_stage_v7', # coupon holder
                8: 'amlab_96_tiprack_1000ul_v3', # Axygen T-1005-WB-C pipette tips in 3D printed tiprack
                6: 'pyrexoffset_2_reservoir_50000ul', # solvent, offset to account for knife stand
                9: 'pyrex_2_reservoir_50000ul', # solution bottle and additive bottle
                11: 'amlab_24_aluminumblock_2000ul_cap',

#                5: 'pyrex_1_reservoir_50000ul', # extra solution for mixing
#                6: 'amlab_24_aluminumblock_2000ul_cap',
#                8: 'opentrons_96_tiprack_1000ul_cut', # Opentrons 1000ul tips with the tips cut off
#                7: 'pyrex_1_reservoir_50000ul',
#                6: 'pyrex_1_reservoir_50000ul', # solution bottle        
#                9: 'pyrex_2_reservoir_50000ul', # polar clean     
#                9: 'pyrex_1_reservoir_50000ul',
                }

# pipetting parameters
# idk who named this but _with means move speed, like how fast the pipette moves in and out of the solution
conf = {
        "viscous":{
                    "asp_rate": 3, "asp_delay": 30, "asp_with": 1, 
                    "disp_rate": 3, "disp_delay": 30, "disp_air_delay": 0.1, "disp_with": 1, "blowout_rate": 8,
                    "mix_asp_rate": 15, "mix_disp_rate": 15, "mix_delay": 0.1, "mix_times": 10, "mix_vol": 820,
                    "air_gap": 10},

                "non-viscous": {
                    "asp_rate": 200, "asp_delay": 0.1, "asp_with": 10,
                    "disp_rate": 400, "disp_delay": 0.1, "disp_air_delay": 0, "disp_with": 10, "blowout_rate": 1000,
                    "mix_asp_rate": 200, "mix_disp_rate": 400, "mix_delay": 0.1, "mix_times": 10, "mix_vol": 820,
                    "air_gap": 10},

                "positional": { ## DO NOT CHANGE UNDER ANY ANY ANY CIRCUMSTANCES!!!
                    "bot_margin_jar": 2,
                    "bot_margin_general": 2
                }
        }

class OT2:
    def __init__(self, dict_of_labware = dict_labware, 
                 #position: Position, 
                 heater:bool = False, tip_index = 0, heater_well_index = 0): # maybe add option to customise the pipette later
        """
        USAGE GUIDELINES:
            It is up to the user's discretion to attach or de-attach a pipette. All of the functions here assume that
                a pipette has been attached.
            Attaching and de-attaching a pipette may be accomplished by the relevant methods provided by this class:
                _attach and _drop.
        """
        # for now the default tiprack location is in slot 8 - multiple default slots can be added
        self.protocol = opentrons.execute.get_protocol_api('2.25')
        
        # configure tipracks and pipette
        self.tipracks = [self.protocol.load_labware(dict_of_labware[8], "8")]
        self.pipette = self.protocol.load_instrument('p1000_single_gen2', 'left', tip_racks=self.tipracks)
        
        # configure everything that is not a tiprack
        self.labware = {}
        self.labware[8] = self.tipracks[0] # placeholder, need sth more concrete esp if multiple tipracks involved
        self.temp_mod = None
        for labware_slot in dict_of_labware:
            if (heater and "aluminumblock" in dict_of_labware[labware_slot]):
                # position the well block on top of the heater
                # crude, but idt anything else needs to be heated, and we only have one heater to begin with...
                # this also assumes that there is only one aluminum block. multiple may be printed in the future - must adjust.
                self.temp_mod = self.protocol.load_module(module_name = "temperature module gen2", location=labware_slot)
                self.temp_wells = self.temp_mod.load_labware(dict_of_labware[labware_slot])
                self.labware[labware_slot] = self.temp_wells
            elif (labware_slot != 8):
                self.labware[labware_slot] = self.protocol.load_labware(dict_of_labware[labware_slot], str(labware_slot))
    
        # home the pipette and reference position object
        self.protocol.home()
        #self.position = position
        
        # set config variable
        self.pipette.flow_rate.aspirate = 1
        self.pipette.flow_rate.dispense = 1
        self.pipette
        self.var = conf

        self.tip_index = tip_index
        self.heater_well_index = heater_well_index
        
    # tier 1 functions
    def has_temp(self):
        return self.temp_mod is not None
   
    def _set_temp(self, temp: float):
        assert self.temp_mod is not None
        self.temp_mod.set_temperature(temp)
        print(f"Temperature set to {temp}.")
        
    def _deactivate_temp(self):
        assert self.temp_mod is not None
        self.temp_mod.deactivate()
    
    def _attach(self, slot_no = None, well_no = None):
        """
        Attaches a pipette tip to the pipette.
        """
        # figure out this functionality!!!
        inc = 0
        while((inc<len(self.pipette.tip_racks)-1) and (self.pipette.tip_racks[inc].next_tip() is not None)):
            inc+=1

        if (slot_no and (well_no >= 0)):
            self.pipette.pick_up_tip(self.labware[slot_no].wells()[well_no])

        else:
            self.pipette.pick_up_tip()
    
    def attach_next_tip(self, slot_no = 8):
        self._attach(slot_no, self.tip_index)
        self.tip_index += 1

    def _drop(self, slot_no = None, well_no = None):
        """
        Drops a pipette tip in a specified slot number and well number. When none are provided, or None is supplied,
            the pipette tip is dropped in the trash.
        It is up to the user to ensure that the labware in the slot number indicated by slot_no is a tip rack.
        """
        if (slot_no and (well_no >= 0)):
            self.pipette.drop_tip(self.labware[slot_no].wells()[well_no])
        else:
#            self.pipette.drop_tip(self.pipette.trash_container.top(z=70)) # pipette tips are very long, discard them very high to help avoid punching a hole in the trash bin
            self.pipette.drop_tip(self.pipette.trash_container.top(z=50)) # the cut opentrons tips are longer, so we'd hit the max z height with 70 mm
            
        
    def _blowout(self, viscous: bool = True):
        """
        Blows out the pipette.
            viscous: bool. Specify true if viscous settings are to be used.
        """
        viscosity = "viscous"
        if (not viscous):
            viscosity = "non-viscous"

        def_pipette = self.pipette.flow_rate.blow_out
        self.pipette.flow_rate.blow_out = self.var[viscosity]["blowout_rate"]
        self.pipette.blow_out()
        self.pipette.flow_rate.blow_out = def_pipette # reset to default blow out rate
           
    def _aspirate_air(self, slot_no, well_no, viscous: bool = True):
        """
        Aspirates air into the pipette. The volume of air aspirated must be constant between different air aspirations
            and can be controlled via conf.ot_var.
        """
        well = self.labware[slot_no].wells()[well_no]
        viscosity = "viscous"
        if (not viscous):
            viscosity = "non-viscous"

        self.pipette.aspirate(self.var[viscosity]["air_gap"], well.top(z=10), rate = self.var[viscosity]["asp_rate"])
    
    def _aspirate(self, slot_no, well_no, vol, viscous: bool = True, for_mixing: bool = False, position: str = "bottom", debug_bypass = 0, lift_after_aspirate=True):
        """
        Aspirates liquid into the pipette.
            viscous: bool. Specify true if viscous settings are to be used.
            for_mixing: bool. Specify true if this is to be used as part of a mixing process. This
                should only be used internally as part of _mix.
        """
        well = self.labware[slot_no].wells()[well_no]
        viscosity = "viscous"
        if (not viscous):
            viscosity = "non-viscous"
        bot_adj = 1
        asp_rate = self.var[viscosity]["asp_rate"]
        if (for_mixing):
            asp_rate = self.var[viscosity]["mix_asp_rate"]
            bot_adj = 4
        if (position != "bottom"): # elevated, if we have more settings next time use a map
            bot_adj += 3 # used to be 7

        # set the z
        if ("pyrex" in self.labware[slot_no].load_name):
            z = self.var["positional"]["bot_margin_jar"] + bot_adj
        else:
            z = self.var["positional"]["bot_margin_general"] + bot_adj

        self.pipette.aspirate(vol, rate=asp_rate, location=well.bottom(z=z))
        
        if (not for_mixing and lift_after_aspirate):
            top_offset = 0
            if debug_bypass == 1:
                  top_offset = 0
            print("entered if statement!!!")
            self.pipette.move_to(well.top(z=top_offset), speed = self.var[viscosity]["asp_with"])
        self.protocol.delay(self.var[viscosity]["asp_delay"])
           
    
    def _dispense(self, slot_no, well_no, vol, viscous: bool = True, for_mixing: bool = False, blow_out: bool = True, \
                  before_air: bool = False, position: str = "bottom"): # dispense custom height?
        """
        Dispenses liquid from the pipette.
            viscous: bool. Specify true if viscous settings are to be used.
            for_mixing: bool. Specify true if this is to be used as part of a mixing process. This
                should only be used internally as part of _mix.
            blow_out: bool. Specify true if the pipette is to blow out after this dispense.
            before_air: bool. Specify true if the pipette is blowing out before aspirating air.
            position: string. Specify "top" if the dispense is to happen at the top of the well.
                    Specify "bottom" if the dispense is to happen at the bottom of the well.
        """
        viscosity = "viscous"
        if (not viscous):
            viscosity = "non-viscous"

        # make well
        well = self.labware[slot_no].wells()[well_no]

        # air aspiration configuration
        if (before_air):
            blow_out = False
        
        # mixing configuration
        bot_adj = 4
        disp_rate = self.var[viscosity]["disp_rate"]
        if (for_mixing):
            disp_rate = self.var[viscosity]["mix_disp_rate"]
            bot_adj = 1
        
        if (not for_mixing): # Assumes that the only business a pipette would have to aspirate and dispense within a well for is to mix.
            self.pipette.move_to(well.top())
        
        # dispense in well at custom dispense flowrate
        if (position.lower() == "bottom"):
            # set the z
            if ("pyrex" in self.labware[slot_no].load_name):
                z = self.var["positional"]["bot_margin_jar"] + bot_adj
            else:
                z = self.var["positional"]["bot_margin_general"] + bot_adj
            self.pipette.move_to(well.bottom(z=z), speed=self.var["non-viscous"]["disp_with"])
            
        else: # dispense top
            # set the z
            if ("aluminumblock" in self.labware[slot_no].load_name): # come up with sth more distinctive...
                z = -40
            else:
                z = 0
            self.pipette.move_to(well.top(z=z), speed=self.var[viscosity]["disp_with"])

        self.pipette.dispense(vol, rate=disp_rate)    
        
        # allow the excess liquid in tip to settle towards tip orifice
        if (before_air and (self.var[viscosity]["disp_air_delay"]>0)):
            self.protocol.delay(self.var[viscosity]["disp_air_delay"])
        else:
            self.protocol.delay(self.var[viscosity]["disp_delay"])

        # lower the blowout rate
        if (blow_out):
            self._blowout(viscous = viscous)

        # movement in mixing is controlled in the _mix() routine.
        # if not mixing, move to the top of the well according to the viscosity setting.
        # note that high surface tension liquids SHOULD BE PIPETTED WITH VISCOUS SETTINGS.
        if (not for_mixing):
            self.pipette.move_to(well.top(z=0), speed=self.var[viscosity]["disp_with"])

    # tier 2 functions
    def _transfer(self, src_slot_no, src_well_no, dest_slot_no, dest_well_no, vol, viscous: bool = True, position: str = "bottom"):
        """
        Transfers liquid from two wells.
            viscous: bool. Specify true if viscous settings are to be used.
            position: string. Specify "top" if the dispense is to happen at the top of the well.
                    Specify "bottom" if the dispense is to happen at the bottom of the well.            
        """
        if (vol > self.pipette.max_volume):
            while(vol - self.pipette.max_volume >= 0):
                vol -= self.pipette.max_volume
                self._aspirate(src_slot_no, src_well_no, self.pipette.max_volume, viscous=viscous)
                self._dispense(dest_slot_no, dest_well_no, self.pipette.max_volume, viscous=viscous, position=position)
            
        self._aspirate(src_slot_no, src_well_no, vol, viscous=viscous)
        self._dispense(dest_slot_no, dest_well_no, vol, viscous=viscous, position=position)

    def _reverse_pipette(self, src_slot_no, src_well_no, dest_slot_no, dest_well_no, vasp = 1000, vdisp = 800, viscous = True, ret_liq_to_src = True, air_gap = False):
        """
        Aspirates an amount of liquid from one well and dispenses less of it in another.
            viscous: bool. Specify true if viscous settings are to be used.
            ret_liq_to_origin: bool. Specify true if the remainder of the liquid in the pipette is to be returned to the source container.
            air_gap: bool. Specify true if the dispense is to be followed with an air aspiration.
        """
        fin_disp = vasp - vdisp

        self._aspirate(src_slot_no, src_well_no, vasp, viscous = viscous)
        self._dispense(dest_slot_no, dest_well_no, vdisp, viscous = viscous, blow_out = False, position = "top", before_air = air_gap)
                                       
        if (air_gap):
            self._aspirate_air(dest_slot_no, dest_well_no, viscous = viscous)
            fin_disp += air_gap

        if (ret_liq_to_src):
            self._dispense(src_slot_no, src_well_no, fin_disp, viscous = viscous, blow_out = True, position = "top")

    def _mix(self, slot_no, well_no, viscous: bool = True, lift_after_aspirate=False): # btw be careful slot_no is one-based well-no is zero based
        """
        Mixes liquids in a well.
            viscous: bool. Specify true if viscous settings are to be used.
        """          
        start = time.perf_counter()
        
        viscosity = "viscous"
        if (not viscous):
            viscosity = "non-viscous"

        for i in range(self.var[viscosity]["mix_times"]):
            #aspirate in well at custom aspirate flowrate
            self._aspirate(slot_no, well_no, self.var[viscosity]["mix_vol"], viscous = viscous, for_mixing = True, lift_after_aspirate = False)
            self.protocol.delay(self.var[viscosity]["mix_delay"])
            
            print("aspirate", i, self.var[viscosity]["mix_times"])

            if (i != self.var[viscosity]["mix_times"]-1):
                #dispense in well at custome dispense flowrate
                self._dispense(slot_no, well_no, self.var[viscosity]["mix_vol"]/2, for_mixing = True, blow_out = False\
                               , viscous = viscous, position = "bottom")
                self._dispense(slot_no, well_no, self.var[viscosity]["mix_vol"]/2, for_mixing = True, blow_out = False\
                               , viscous = viscous, position = "top")

                #allow the excess liquid in tip to settle towards tip orifice
                self.protocol.delay(self.var[viscosity]["mix_delay"])
            else:
                self._dispense(slot_no, well_no, self.var[viscosity]["mix_vol"]/2, for_mixing = True, blow_out = False\
                               , viscous = viscous, position = "bottom")
                self._dispense(slot_no, well_no, self.var[viscosity]["mix_vol"]/2, for_mixing = True, blow_out = True\
                               , viscous = viscous, position = "top")
                self.protocol.delay(self.var[viscosity]["mix_delay"])
            
            # instead of not using mix settings, use mix settings but don't blow out
            # TODO
            
            print("dispense", i, self.var[viscosity]["mix_times"])
            
        # make well
        well = self.labware[slot_no].wells()[well_no]
        
        end = time.perf_counter()
        print(end-start)
        
    def prep_pullcast(self, slot_no, well_no, vol, viscous: bool = True):
        if (vol > 450):
            self.prep_pullcast_asperate(slot_no, well_no, vol, viscous)
            self.prep_pullcast_dispense(vol)
        else:
            print("unsafe volume for pullcasting!")
    
    def prep_pullcast_asperate(self, slot_no, well_no, vol, viscous: bool = True):
        self._aspirate(slot_no, well_no, vol/2, viscous, position="elevated", lift_after_aspirate = False)
        self._aspirate(slot_no, well_no, vol/2, viscous, position="bottom")
    
    def prep_pullcast_dispense(self, vol):
        volumes = [vol/6 - 60, vol/6 - 20, vol/6 - 10, vol/6 + 10, vol/6 + 20, vol/6 + 60]
        for i in range(6):
            blow_out = False
            if (i==5): blow_out = True
            self._dispense(1, i, volumes[i], viscous = False, blow_out = blow_out)

    def prep_pullcast_from_mix(self, vol, viscous: bool = True):
        self.prep_pullcast(heater_slot_no, self.heater_well_index, vol, viscous)
        self.heater_well_index += 1
    
    def prep_pullcast_from_mix_asperate(self, vol, viscous: bool = True):
        self.prep_pullcast_asperate(heater_slot_no, self.heater_well_index, vol, viscous)
        self.heater_well_index += 1

    """"
    # assume no pippette tip to begin, but does not drop tip at the end (we'll use the same tip for pullcast)
    def _prepare_solution(self, desired_weight_percent, total_vol, viscous: bool = True, position: str = "bottom"):
        rho_solution = 1.114867
        rho_solvent = 1.0148
        C_i = polymer_stock_wt_percent/100
        C_f = desired_weight_percent/100
        V_f = total_vol
        V_c = round(((C_i-C_f)*V_f*rho_solution)/(C_i*rho_solution - C_f*rho_solution + C_f*rho_solvent),0)
        V_i = round(V_f - V_c,0)
        print(f"Solvent: {V_c} uL", f"Solution: {V_i} uL")
        if total_vol > 1000:
            # raise error
            raise ValueError("Final volume cannot exceed 1000 µL.")
        
        # actually mix the solution
        if V_c != 0:
            self.attach_next_tip()
            self._transfer(solvent_slot_no, solvent_well_no, heater_slot_no, self.heater_well_index, V_c, False)
            self._drop()
            self.attach_next_tip()
            self._transfer(solution_slot_no, solution_well_no, heater_slot_no, self.heater_well_index, V_i)
            self._mix(heater_slot_no, self.heater_well_index)
        else: # no mixing required if desired weight percent is same as the stock
            self.attach_next_tip()
            self._transfer(solution_slot_no, solution_well_no, heater_slot_no, self.heater_well_index, V_i)
        
    """        

    def prepare_membrane_solution(self, total_vol, target_polymer_wt_percent, target_additive_wt_percent, mixing_temp):
        # declare variables to pass to function
        target_recipe = calc.TargetRecipe(total_vol, target_polymer_wt_percent, target_additive_wt_percent)
        stock = calc.StockParameters(polymer_stock_wt_percent, additive_stock_polymer_wt_percent, additive_stock_additive_wt_percent)

        # get and display result
        result = calc.calculate_batch(target_recipe, stock)
        calc.print_result(target_recipe, result)

        # convert to result normal variables
        V_normal_polymer = result.normal_polymer_stock_uL
        V_additive_polymer = result.polymer_additive_stock_uL
        V_solvent = result.solvent_uL

        # only additive solution
        if V_additive_polymer == total_vol:
            print("Solution will be pulled from additive bottle.")
            self.attach_next_tip()
            self.prep_pullcast_asperate(additive_1_slot_no, additive_1_well_no, total_vol)

        # only polymer solution
        elif V_normal_polymer == total_vol:
            print("Solution will be pulled from stock polymer bottle.")
            self.attach_next_tip()
            self.prep_pullcast_asperate(solution_slot_no, solution_well_no, total_vol)

        # only solvent, not sure if this would ever happen but just incase
        elif V_solvent == total_vol:
            print("Only solvent will be used. If this is an error, correct it ASAP.")
            self.attach_next_tip()
            self.prep_pullcast_asperate(solvent_slot_no, solvent_well_no, total_vol)
        
        # else, solution must be mixed
        else:
            # set mixing temperature
            if(self.has_temp()):
                self._set_temp(mixing_temp)

            # add solvent to well
            if V_solvent > 0:
                self.attach_next_tip()
                self._transfer(solvent_slot_no, solvent_well_no, heater_slot_no, self.heater_well_index, V_solvent, False)
                self._drop()

            # add additive solution to well
            if V_additive_polymer > 0:
                self.attach_next_tip()
                self._transfer(additive_1_slot_no, additive_1_well_no, heater_slot_no, self.heater_well_index, V_additive_polymer)
                
            # add stock solution to well
            if V_normal_polymer > 0:
                if V_additive_polymer > 0:
                    self._drop() # only drop tip if additive solution used
                self.attach_next_tip()
                self._transfer(solution_slot_no, solution_well_no, heater_slot_no, self.heater_well_index, V_normal_polymer)
            
            # mix solution and prep for pullcast
            self._mix(heater_slot_no, self.heater_well_index)
            self.prep_pullcast_from_mix_asperate(total_vol, True)
        
        # deactivate opentrons heater when done mixing
        if(self.has_temp()):
            self._deactivate_temp()

    """    
    def _prepare_additive_solution(self, total_vol, target_polymer_wt_percent, target_additive_wt_percent):
        rho_solvent = 1.0148
        rho_polymer_stock = 1.114867
        rho_additive_polymer_stock = 1.114867 # update when actual value is known

        Cp_f = target_polymer_wt_percent / 100
        Ca_f = target_additive_wt_percent / 100

        Cp_i = polymer_stock_wt_percent / 100
        Ca_i = additive_stock_additive_wt_percent / 100

        rho_p = rho_polymer_stock
        rho_a = rho_additive_polymer_stock
        rho_s = rho_solvent

        # raise errors
        if total_vol <= 0:
            raise ValueError("Total volume must be positive.")
        if total_vol > 1000:
            raise ValueError("Final volume cannot exceed 1000 µL.")
        if target_polymer_wt_percent <= 0:
            raise ValueError("Target polymer concentration must be positive.")
        if target_polymer_wt_percent > polymer_stock_wt_percent:
            raise ValueError("Target polymer concentration cannot exceed stock polymer concentration.")
        if target_additive_wt_percent < 0:
            raise ValueError("Target additive concentration cannot be negative.")
        if target_additive_wt_percent > additive_stock_additive_wt_percent:
            raise ValueError("Target additive concentration cannot exceed additive stock concentration.")

        A = np.array([
        [(Cp_i - Cp_f) * rho_p,
            (Cp_i - Cp_f) * rho_a,
            -Cp_f * rho_s,],
        [-Ca_f * rho_p,
            (Ca_i - Ca_f) * rho_a,
            -Ca_f * rho_s,],
        [1, 1, 1,],
        ])

        b = np.array([0, 0, total_vol])

        V_normal_polymer, V_additive_polymer, V_solvent = np.linalg.solve(A, b)

        if (V_normal_polymer < -1e-6or V_additive_polymer < -1e-6 or V_solvent < -1e-6):
            raise ValueError(
                "Impossible formulation. Calculated negative volume:\n"
                f"Normal polymer stock: {V_normal_polymer:.2f} uL\n"
                f"Additive polymer stock: {V_additive_polymer:.2f} uL\n"
                f"Solvent: {V_solvent:.2f} uL")

        V_normal_polymer = max(V_normal_polymer, 0)
        V_additive_polymer = max(V_additive_polymer, 0)
        V_solvent = max(V_solvent, 0)

        # round to nearest uL
        V_normal_polymer = round(V_normal_polymer, 0)
        V_additive_polymer = round(V_additive_polymer, 0)
        V_solvent = round(total_vol - V_normal_polymer - V_additive_polymer, 0)
        
        # print volume amounts
        print(f"Stock volume: {V_normal_polymer}")
        print(f"Additive volume: {V_additive_polymer}")
        print(f"Solvent volume: {V_solvent}")
        print(f"\nWeight percent: {(V_normal_polymer + V_additive_polymer) * polymer_stock_wt_percent * 0.001}")
        print(f"Additive percent: {V_additive_polymer * additive_stock_additive_wt_percent * 0.001}")
        
        # mix the solution
        if V_normal_polymer != 0 or V_additive_polymer != 0 or V_solvent != 0:
            # add solvent to well
            if V_solvent > 0:
                self.attach_next_tip()
                self._transfer(solvent_slot_no, solvent_well_no, heater_slot_no, self.heater_well_index, V_solvent, False)
                self._drop()
            # add additive solution to well
            if V_additive_polymer > 0:
                self.attach_next_tip()
                self._transfer(additive_1_slot_no, additive_1_well_no, heater_slot_no, self.heater_well_index, V_additive_polymer)
                self._drop()
            # add stock solution to well
            if V_normal_polymer > 0:
                self.attach_next_tip()
                self._transfer(solution_slot_no, solution_well_no, heater_slot_no, self.heater_well_index, V_normal_polymer)
                self._mix(heater_slot_no, self.heater_well_index)
        
    """            

    def runhome(self):
        self.protocol.home()
        if self.pipette.has_tip:
            self.pipette.drop_tip()

    def update_metadata(self, params):
        polymer_stock_wt_percent = params["polymer_stock_wt_percent"]
        additive_stock_additive_wt_percent = params["additive_stock_additive_wt_percent"]
        additive_stock_polymer_wt_percent = params["additive_stock_polymer_wt_percent"]

    def get_stock_weight_percent(self):
        return polymer_stock_wt_percent
                           
    def get_additive_percent(self):
        return additive_stock_additive_wt_percent
    
    def get_additive_polymer_percent(self):
        return additive_stock_polymer_wt_percent
