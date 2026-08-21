import time
import os
from opentrons import protocol_api
import opentrons.execute
import numpy as np
import calculations as calc
from bottle_inventory import BottleInventory

polymer_stock_pwt = 17.0
solvents_cswt = 30.0
all_mix_pwt = 17.0
all_mix_cswt = 24.9
legacy_polymer_stock_wt_percent = 17.0
legacy_additive_stock_polymer_wt_percent = 17.0
legacy_additive_stock_additive_wt_percent = 4.0

# Edit these when bottle capacity or the required aspiration reserve changes. On first use,
# these values create bottle_inventory.json one directory above this file. Subsequent restarts
# load the saved remaining volumes instead of resetting them.
INITIAL_BOTTLE_VOLUMES_UL = {
    "polymer_stock": 20000.0,
    "solvent_additive_stock": 20000.0,
    "all_mix_stock": 20000.0,
    "solvent": 20000.0,
}
DEAD_VOLUMES_UL = {name: 2000.0 for name in INITIAL_BOTTLE_VOLUMES_UL}
INVENTORY_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bottle_inventory.json"))

solution_slot_no = 9
solution_well_no = 0
solvent_slot_no = 6
solvent_well_no = 0
heater_slot_no = 11
solvent_additive_slot_no = 6
solvent_additive_well_no = 1
all_mix_slot_no = 9
all_mix_well_no = 1

dict_labware = {
                1: 'amlab_cast_stage_v7', # coupon holder
                8: 'amlab_96_tiprack_1000ul_v3', # Axygen T-1005-WB-C pipette tips in 3D printed tiprack
                6: 'pyrexoffset_2_reservoir_50000ul', # solvent and solvent-additive
                9: 'pyrex_2_reservoir_50000ul', # polymer stock and all-mix stock
                11: 'amlab_24_aluminumblock_2000ul_cap',
                #9: 'vial_8_reservoir_20000ul', # vial holder

                # add more labware with following template
                # slot_num: 'labware_file_name',
                # ensure labware is in labware folder
                }

# pipetting parameters
# _with means move speed, how fast the pipette moves in and out of the solution
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
        
        # solution variables
        self.polymer_stock_pwt = polymer_stock_pwt
        self.solvents_cswt = solvents_cswt
        self.all_mix_pwt = all_mix_pwt
        self.all_mix_cswt = all_mix_cswt
        self.polymer_stock_wt_percent = legacy_polymer_stock_wt_percent
        self.additive_stock_polymer_wt_percent = legacy_additive_stock_polymer_wt_percent
        self.additive_stock_additive_wt_percent = legacy_additive_stock_additive_wt_percent
        self.stock_mode = "four_bottle"
        self.bottle_inventory = BottleInventory(
            INVENTORY_PATH, INITIAL_BOTTLE_VOLUMES_UL, DEAD_VOLUMES_UL)

    # ==================================================
    # SECTION: Tier 1 Functions
    # ==================================================        
    
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
        inc = 0
        while((inc<len(self.pipette.tip_racks)-1) and (self.pipette.tip_racks[inc].next_tip() is not None)):
            inc+=1

        if (slot_no and (well_no >= 0)):
            self.pipette.pick_up_tip(self.labware[slot_no].wells()[well_no])

        else:
            self.pipette.pick_up_tip()

    def _drop(self, slot_no = None, well_no = None):
        """
        Drops a pipette tip in a specified slot number and well number. When none are provided, or None is supplied,
            the pipette tip is dropped in the trash.
        It is up to the user to ensure that the labware in the slot number indicated by slot_no is a tip rack.
        """
        if (slot_no and (well_no >= 0)):
            self.pipette.drop_tip(self.labware[slot_no].wells()[well_no])
        else:           
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

    # ==================================================
    # SECTION: Tier 2 Functions
    # ==================================================

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

            if (i != self.var[viscosity]["mix_times"] - 1):
                #dispense in well at custome dispense flowrate
                self._dispense(slot_no, well_no, self.var[viscosity]["mix_vol"]/2, for_mixing = True, blow_out = False\
                               , viscous = viscous, position = "bottom")
                self._dispense(slot_no, well_no, self.var[viscosity]["mix_vol"]/2, for_mixing = True, blow_out = False\
                               , viscous = viscous, position = "top")

                # allow the excess liquid in tip to settle towards tip orifice
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

    def attach_next_tip(self, slot_no = 8):
        self._attach(slot_no, self.tip_index)
        self.tip_index += 1

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

    def runhome(self):
        self.protocol.home()
        if self.pipette.has_tip:
            self.pipette.drop_tip()

    def update_metadata(self, params):
        mode = params.get("stock_mode")
        if mode is None:
            mode = "two_bottle" if "polymer_stock_wt_percent" in params else "four_bottle"
        if mode == "four_bottle":
            self.polymer_stock_pwt = params["polymer_stock_pwt"]
            self.solvents_cswt = params["solvents_cswt"]
            self.all_mix_pwt = params["all_mix_pwt"]
            self.all_mix_cswt = params["all_mix_cswt"]
        elif mode == "two_bottle":
            self.polymer_stock_wt_percent = params["polymer_stock_wt_percent"]
            self.additive_stock_polymer_wt_percent = params["additive_stock_polymer_wt_percent"]
            self.additive_stock_additive_wt_percent = params["additive_stock_additive_wt_percent"]
        else:
            raise ValueError("Unknown stock mode: {}".format(mode))
        self.stock_mode = mode

    # return values
    def get_stock_weight_percent(self):
        if self.stock_mode == "two_bottle":
            return self.polymer_stock_wt_percent
        return self.polymer_stock_pwt
    def get_additive_percent(self):
        if self.stock_mode == "two_bottle":
            return self.additive_stock_additive_wt_percent
        return self.solvents_cswt
    def get_additive_polymer_percent(self):
        if self.stock_mode == "two_bottle":
            return self.additive_stock_polymer_wt_percent
        return self.all_mix_pwt

    def get_bottle_inventory(self):
        """Return remaining, reserved, and usable volume for each stock bottle."""
        return self.bottle_inventory.snapshot()

    def set_bottle_remaining_volume(self, bottle, volume_uL):
        """Reconcile inventory after physically measuring, refilling, or replacing a bottle."""
        self.bottle_inventory.set_remaining(bottle, volume_uL)
        print("Updated bottle inventory: {}".format(self.bottle_inventory.snapshot()))

    # ==================================================
    # SECTION: Tier 3 Functions
    # ==================================================    

    def prepare_membrane_solution(self, total_vol, target_polymer_wt_percent, target_additive_wt_percent, mixing_temp):
        target_recipe = calc.TargetRecipe(total_vol, target_polymer_wt_percent, target_additive_wt_percent)
        if self.stock_mode == "two_bottle":
            stock = calc.LegacyStockParameters(
                polymer_stock_wt_percent=self.polymer_stock_wt_percent,
                additive_stock_polymer_wt_percent=self.additive_stock_polymer_wt_percent,
                additive_stock_additive_wt_percent=self.additive_stock_additive_wt_percent,
            )
        else:
            stock = calc.StockParameters(
                polymer_stock_pwt=self.polymer_stock_pwt,
                solvents_cswt=self.solvents_cswt,
                all_mix_pwt=self.all_mix_pwt,
                all_mix_cswt=self.all_mix_cswt,
            )
        result = calc.calculate_batch(target_recipe, stock)
        calc.print_result(target_recipe, result)

        if self.stock_mode == "two_bottle":
            sources = [
                ("polymer_stock", "polymer stock", solution_slot_no, solution_well_no,
                 result.normal_polymer_stock_uL, True),
                # Legacy bottle 2 shares the all-mix bottle's physical position and inventory key.
                ("all_mix_stock", "polymer-additive stock", all_mix_slot_no, all_mix_well_no,
                 result.polymer_additive_stock_uL, True),
                ("solvent", "pure solvent", solvent_slot_no, solvent_well_no,
                 result.solvent_uL, False),
            ]
        else:
            sources = [
                ("polymer_stock", "polymer stock", solution_slot_no, solution_well_no,
                 result.polymer_stock_uL, True),
                ("solvent_additive_stock", "solvent-additive stock", solvent_additive_slot_no, solvent_additive_well_no,
                 result.cosolvent_stock_uL, False),
                ("all_mix_stock", "all-mix stock", all_mix_slot_no, all_mix_well_no,
                 result.all_mix_stock_uL, True),
                ("solvent", "pure solvent", solvent_slot_no, solvent_well_no,
                 result.solvent_uL, False),
            ]
        active_sources = [source for source in sources if source[4] > 0]
        self.bottle_inventory.require({source[0]: source[4] for source in active_sources})
        print("Bottle inventory before preparation: {}".format(self.bottle_inventory.snapshot()))

        if len(active_sources) == 1 and abs(active_sources[0][4] - total_vol) < 1e-6:
            bottle, name, slot, well, volume, viscous = active_sources[0]
            print("Solution will be pulled directly from the {} bottle.".format(name))
            self.attach_next_tip()
            self.prep_pullcast_asperate(slot, well, volume, viscous)
            self.bottle_inventory.consume(bottle, volume)
        else:
            tip = False
            if(self.has_temp()):
                self._set_temp(mixing_temp)

            for bottle, name, slot, well, volume, viscous in active_sources:
                if tip:
                    self._drop()
                self.attach_next_tip()
                tip = True
                print("Adding {:.2f} uL from {}.".format(volume, name))
                self._transfer(slot, well, heater_slot_no, self.heater_well_index, volume, viscous)
                self.bottle_inventory.consume(bottle, volume)

            self._mix(heater_slot_no, self.heater_well_index)
            self.prep_pullcast_from_mix_asperate(total_vol, True)

        print("Bottle inventory after preparation: {}".format(self.bottle_inventory.snapshot()))
        
        # deactivate opentrons heater when done mixing
        if(self.has_temp()):
            self._deactivate_temp()

