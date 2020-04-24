# Copyright 2019-2020 the openage authors. See copying.md for legal info.

"""
Convert data from AoC to openage formats.
"""
from ...dataformat.aoc.genie_object_container import GenieObjectContainer
from ...dataformat.aoc.genie_unit import GenieUnitObject
from ...dataformat.aoc.genie_tech import GenieTechObject
from ...dataformat.aoc.genie_effect import GenieEffectObject,\
    GenieEffectBundle
from ...dataformat.aoc.genie_civ import GenieCivilizationObject
from ...dataformat.aoc.genie_connection import GenieAgeConnection,\
    GenieBuildingConnection, GenieUnitConnection, GenieTechConnection
from ...dataformat.aoc.genie_graphic import GenieGraphic
from ...dataformat.aoc.genie_sound import GenieSound
from ...dataformat.aoc.genie_terrain import GenieTerrainObject
from ...dataformat.aoc.genie_unit import GenieUnitLineGroup,\
    GenieUnitTransformGroup, GenieMonkGroup
from ...dataformat.aoc.genie_unit import GenieStackBuildingGroup,\
    GenieBuildingLineGroup
from ...dataformat.aoc.genie_tech import AgeUpgrade,\
    UnitUnlock, UnitLineUpgrade, CivBonus
from ...dataformat.aoc.genie_civ import GenieCivilizationGroup
from ...dataformat.aoc.genie_unit import GenieUnitTaskGroup,\
    GenieVillagerGroup
from ...dataformat.aoc.genie_tech import BuildingLineUpgrade

from ...dataformat.aoc.genie_unit import GenieVariantGroup
from .nyan_subprocessor import AoCNyanSubprocessor
from ...nyan.api_loader import load_api
from .modpack_subprocessor import AoCModpackSubprocessor
from openage.convert.processor.aoc.media_subprocessor import AoCMediaSubprocessor
from openage.convert.dataformat.aoc.genie_tech import StatUpgrade, InitiatedTech,\
    BuildingUnlock
from openage.convert.processor.aoc.pregen_processor import AoCPregenSubprocessor
from openage.convert.dataformat.aoc.internal_nyan_names import AMBIENT_GROUP_LOOKUPS,\
    VARIANT_GROUP_LOOKUPS
from openage.convert.dataformat.aoc.genie_unit import GenieAmbientGroup,\
    GenieGarrisonMode

from ....log import info
from openage.convert.dataformat.aoc.genie_terrain import GenieTerrainGroup


class AoCProcessor:

    @classmethod
    def convert(cls, gamespec):
        """
        Input game speification and media here and get a set of
        modpacks back.

        :param gamespec: Gamedata from empires.dat read in by the
                         reader functions.
        :type gamespec: class: ...dataformat.value_members.ArrayMember
        :returns: A list of modpacks.
        :rtype: list
        """

        info("Starting conversion...")

        # Create a new container for the conversion process
        data_set = cls._pre_processor(gamespec)

        # Create the custom openae formats (nyan, sprite, terrain)
        data_set = cls._processor(data_set)

        # Create modpack definitions
        modpacks = cls._post_processor(data_set)

        return modpacks

    @classmethod
    def _pre_processor(cls, gamespec):
        """
        Store data from the reader in a conversion container.

        :param gamespec: Gamedata from empires.dat file.
        :type gamespec: class: ...dataformat.value_members.ArrayMember
        """
        data_set = GenieObjectContainer()

        data_set.nyan_api_objects = load_api()

        info("Extracting Genie data...")

        cls._extract_genie_units(gamespec, data_set)
        cls._extract_genie_techs(gamespec, data_set)
        cls._extract_genie_effect_bundles(gamespec, data_set)
        cls._sanitize_effect_bundles(data_set)
        cls._extract_genie_civs(gamespec, data_set)
        cls._extract_age_connections(gamespec, data_set)
        cls._extract_building_connections(gamespec, data_set)
        cls._extract_unit_connections(gamespec, data_set)
        cls._extract_tech_connections(gamespec, data_set)
        cls._extract_genie_graphics(gamespec, data_set)
        cls._extract_genie_sounds(gamespec, data_set)
        cls._extract_genie_terrains(gamespec, data_set)

        return data_set

    @classmethod
    def _processor(cls, full_data_set):
        """
        1. Transfer structures used in Genie games to more openage-friendly
           Python objects.
        2. Convert these objects to nyan.

        :param full_data_set: GenieObjectContainer instance that
                              contains all relevant data for the conversion
                              process.
        :type full_data_set: class: ...dataformat.aoc.genie_object_container.GenieObjectContainer
        """

        info("Creating API-like objects...")

        cls._create_unit_lines(full_data_set)
        cls._create_extra_unit_lines(full_data_set)
        cls._create_building_lines(full_data_set)
        cls._create_villager_groups(full_data_set)
        cls._create_ambient_groups(full_data_set)
        cls._create_variant_groups(full_data_set)
        cls._create_terrain_groups(full_data_set)
        cls._create_tech_groups(full_data_set)
        cls._create_civ_groups(full_data_set)

        info("Linking API-like objects...")

        cls._link_building_upgrades(full_data_set)
        cls._link_creatables(full_data_set)
        cls._link_researchables(full_data_set)
        cls._link_civ_uniques(full_data_set)
        cls._link_resources_to_dropsites(full_data_set)
        cls._link_garrison(full_data_set)
        cls._link_trade_posts(full_data_set)

        info("Generating auxiliary objects...")

        AoCPregenSubprocessor.generate(full_data_set)

        return full_data_set

    @classmethod
    def _post_processor(cls, full_data_set):

        info("Creating nyan objects...")

        AoCNyanSubprocessor.convert(full_data_set)

        info("Creating requests for media export...")

        AoCMediaSubprocessor.convert(full_data_set)

        return AoCModpackSubprocessor.get_modpacks(full_data_set)

    @staticmethod
    def _extract_genie_units(gamespec, full_data_set):
        """
        Extract units from the game data.

        :param gamespec: Gamedata from empires.dat file.
        :type gamespec: class: ...dataformat.value_members.ArrayMember
        """
        # Units are stored in the civ container.
        # All civs point to the same units (?) except for Gaia which has more.
        # Gaia also seems to have the most units, so we only read from Gaia
        #
        # call hierarchy: wrapper[0]->civs[0]->units
        raw_units = gamespec.get_value()[0].get_value()["civs"].get_value()[0]\
            .get_value()["units"].get_value()

        # Unit headers store the things units can do
        raw_unit_headers = gamespec.get_value()[0].get_value()["unit_headers"].get_value()

        for raw_unit in raw_units:
            unit_id = raw_unit.get_value()["id0"].get_value()
            unit_members = raw_unit.get_value()

            # Turn attack and armor into containers to make diffing work
            if "attacks" in unit_members.keys():
                attacks_member = unit_members.pop("attacks")
                attacks_member = attacks_member.get_container("type_id")
                armors_member = unit_members.pop("armors")
                armors_member = armors_member.get_container("type_id")

                unit_members.update({"attacks": attacks_member})
                unit_members.update({"armors": armors_member})

            unit = GenieUnitObject(unit_id, full_data_set, members=unit_members)
            full_data_set.genie_units.update({unit.get_id(): unit})

            # Commands
            unit_commands = raw_unit_headers[unit_id].get_value()["unit_commands"]
            unit.add_member(unit_commands)

    @staticmethod
    def _extract_genie_techs(gamespec, full_data_set):
        """
        Extract techs from the game data.

        :param gamespec: Gamedata from empires.dat file.
        :type gamespec: class: ...dataformat.value_members.ArrayMember
        """
        # Techs are stored as "researches".
        #
        # call hierarchy: wrapper[0]->researches
        raw_techs = gamespec.get_value()[0].get_value()["researches"].get_value()

        index = 0
        for raw_tech in raw_techs:
            tech_id = index
            tech_members = raw_tech.get_value()

            tech = GenieTechObject(tech_id, full_data_set, members=tech_members)
            full_data_set.genie_techs.update({tech.get_id(): tech})

            index += 1

    @staticmethod
    def _extract_genie_effect_bundles(gamespec, full_data_set):
        """
        Extract effects and effect bundles from the game data.

        :param gamespec: Gamedata from empires.dat file.
        :type gamespec: class: ...dataformat.value_members.ArrayMember
        """
        # call hierarchy: wrapper[0]->effect_bundles
        raw_effect_bundles = gamespec.get_value()[0].get_value()["effect_bundles"].get_value()

        index_bundle = 0
        for raw_effect_bundle in raw_effect_bundles:
            bundle_id = index_bundle

            # call hierarchy: effect_bundle->effects
            raw_effects = raw_effect_bundle.get_value()["effects"].get_value()

            effects = {}

            index_effect = 0
            for raw_effect in raw_effects:
                effect_id = index_effect
                effect_members = raw_effect.get_value()

                effect = GenieEffectObject(effect_id, bundle_id, full_data_set,
                                           members=effect_members)

                effects.update({effect_id: effect})

                index_effect += 1

            # Pass everything to the bundle
            effect_bundle_members = raw_effect_bundle.get_value()
            # Remove effects we store them as separate objects
            effect_bundle_members.pop("effects")

            bundle = GenieEffectBundle(bundle_id, effects, full_data_set,
                                       members=effect_bundle_members)
            full_data_set.genie_effect_bundles.update({bundle.get_id(): bundle})

            index_bundle += 1

    @staticmethod
    def _extract_genie_civs(gamespec, full_data_set):
        """
        Extract civs (without units) from the game data.

        :param gamespec: Gamedata from empires.dat file.
        :type gamespec: class: ...dataformat.value_members.ArrayMember
        """
        # call hierarchy: wrapper[0]->civs
        raw_civs = gamespec.get_value()[0].get_value()["civs"].get_value()

        index = 0
        for raw_civ in raw_civs:
            civ_id = index

            civ_members = raw_civ.get_value()
            units_member = civ_members.pop("units")
            units_member = units_member.get_container("id0")

            civ_members.update({"units": units_member})

            civ = GenieCivilizationObject(civ_id, full_data_set, members=civ_members)
            full_data_set.genie_civs.update({civ.get_id(): civ})

            index += 1

    @staticmethod
    def _extract_age_connections(gamespec, full_data_set):
        """
        Extract age connections from the game data.

        :param gamespec: Gamedata from empires.dat file.
        :type gamespec: class: ...dataformat.value_members.ArrayMember
        """
        # call hierarchy: wrapper[0]->age_connections
        raw_connections = gamespec.get_value()[0].get_value()["age_connections"].get_value()

        for raw_connection in raw_connections:
            age_id = raw_connection.get_value()["id"].get_value()
            connection_members = raw_connection.get_value()

            connection = GenieAgeConnection(age_id, full_data_set, members=connection_members)
            full_data_set.age_connections.update({connection.get_id(): connection})

    @staticmethod
    def _extract_building_connections(gamespec, full_data_set):
        """
        Extract building connections from the game data.

        :param gamespec: Gamedata from empires.dat file.
        :type gamespec: class: ...dataformat.value_members.ArrayMember
        """
        # call hierarchy: wrapper[0]->building_connections
        raw_connections = gamespec.get_value()[0].get_value()["building_connections"].get_value()

        for raw_connection in raw_connections:
            building_id = raw_connection.get_value()["id"].get_value()
            connection_members = raw_connection.get_value()

            connection = GenieBuildingConnection(building_id, full_data_set,
                                                 members=connection_members)
            full_data_set.building_connections.update({connection.get_id(): connection})

    @staticmethod
    def _extract_unit_connections(gamespec, full_data_set):
        """
        Extract unit connections from the game data.

        :param gamespec: Gamedata from empires.dat file.
        :type gamespec: class: ...dataformat.value_members.ArrayMember
        """
        # call hierarchy: wrapper[0]->unit_connections
        raw_connections = gamespec.get_value()[0].get_value()["unit_connections"].get_value()

        for raw_connection in raw_connections:
            unit_id = raw_connection.get_value()["id"].get_value()
            connection_members = raw_connection.get_value()

            connection = GenieUnitConnection(unit_id, full_data_set, members=connection_members)
            full_data_set.unit_connections.update({connection.get_id(): connection})

    @staticmethod
    def _extract_tech_connections(gamespec, full_data_set):
        """
        Extract tech connections from the game data.

        :param gamespec: Gamedata from empires.dat file.
        :type gamespec: class: ...dataformat.value_members.ArrayMember
        """
        # call hierarchy: wrapper[0]->tech_connections
        raw_connections = gamespec.get_value()[0].get_value()["tech_connections"].get_value()

        for raw_connection in raw_connections:
            tech_id = raw_connection.get_value()["id"].get_value()
            connection_members = raw_connection.get_value()

            connection = GenieTechConnection(tech_id, full_data_set, members=connection_members)
            full_data_set.tech_connections.update({connection.get_id(): connection})

    @staticmethod
    def _extract_genie_graphics(gamespec, full_data_set):
        """
        Extract graphic definitions from the game data.

        :param gamespec: Gamedata from empires.dat file.
        :type gamespec: class: ...dataformat.value_members.ArrayMember
        """
        # call hierarchy: wrapper[0]->graphics
        raw_graphics = gamespec.get_value()[0].get_value()["graphics"].get_value()

        for raw_graphic in raw_graphics:
            # Can be ignored if there is no filename associated
            filename = raw_graphic.get_value()["filename"].get_value()
            if not filename:
                continue

            graphic_id = raw_graphic.get_value()["graphic_id"].get_value()
            graphic_members = raw_graphic.get_value()

            graphic = GenieGraphic(graphic_id, full_data_set, members=graphic_members)
            full_data_set.genie_graphics.update({graphic.get_id(): graphic})

        # Detect subgraphics
        for genie_graphic in full_data_set.genie_graphics.values():
            genie_graphic.detect_subgraphics()

    @staticmethod
    def _extract_genie_sounds(gamespec, full_data_set):
        """
        Extract sound definitions from the game data.

        :param gamespec: Gamedata from empires.dat file.
        :type gamespec: class: ...dataformat.value_members.ArrayMember
        """
        # call hierarchy: wrapper[0]->sounds
        raw_sounds = gamespec.get_value()[0].get_value()["sounds"].get_value()

        for raw_sound in raw_sounds:
            sound_id = raw_sound.get_value()["sound_id"].get_value()
            sound_members = raw_sound.get_value()

            sound = GenieSound(sound_id, full_data_set, members=sound_members)
            full_data_set.genie_sounds.update({sound.get_id(): sound})

    @staticmethod
    def _extract_genie_terrains(gamespec, full_data_set):
        """
        Extract terrains from the game data.

        :param gamespec: Gamedata from empires.dat file.
        :type gamespec: class: ...dataformat.value_members.ArrayMember
        """
        # call hierarchy: wrapper[0]->terrains
        raw_terrains = gamespec.get_value()[0].get_value()["terrains"].get_value()

        index = 0
        for raw_terrain in raw_terrains:
            terrain_index = index
            terrain_members = raw_terrain.get_value()

            terrain = GenieTerrainObject(terrain_index, full_data_set, members=terrain_members)
            full_data_set.genie_terrains.update({terrain.get_id(): terrain})

            index += 1

    @staticmethod
    def _create_unit_lines(full_data_set):
        """
        Sort units into lines, based on information in the unit connections.

        :param full_data_set: GenieObjectContainer instance that
                              contains all relevant data for the conversion
                              process.
        :type full_data_set: class: ...dataformat.aoc.genie_object_container.GenieObjectContainer
        """

        unit_connections = full_data_set.unit_connections

        # Stores unit lines with key=line_id and val=object
        # while they are created. In the GenieObjectContainer,
        # we additionally store them with key=head_unit_id
        # and val=object.
        pre_unit_lines = {}

        for connection in unit_connections.values():
            unit_id = connection.get_member("id").get_value()
            unit = full_data_set.genie_units[unit_id]
            line_id = connection.get_member("vertical_line").get_value()

            # Check if a line object already exists for this id
            # if not, create it
            if line_id in pre_unit_lines.keys():
                unit_line = pre_unit_lines[line_id]
                full_data_set.unit_ref.update({unit_id: unit_line})

            else:
                # Check for special cases first
                if unit.has_member("transform_unit_id")\
                        and unit.get_member("transform_unit_id").get_value() > -1:
                    # Trebuchet
                    unit_line = GenieUnitTransformGroup(line_id, unit_id, full_data_set)
                    full_data_set.transform_groups.update({unit_line.get_id(): unit_line})

                elif line_id == 65:
                    # Monks
                    # Switch to monk with relic is hardcoded :(
                    unit_line = GenieMonkGroup(line_id, unit_id, 286, full_data_set)
                    full_data_set.monk_groups.update({unit_line.get_id(): unit_line})

                elif unit.has_member("task_group")\
                        and unit.get_member("task_group").get_value() > 0:
                    # Villager
                    # done somewhere else because they are special^TM
                    continue

                else:
                    # Normal units
                    unit_line = GenieUnitLineGroup(line_id, full_data_set)

                pre_unit_lines.update({unit_line.get_id(): unit_line})
                full_data_set.unit_ref.update({unit_id: unit_line})

            if connection.get_member("line_mode").get_value() == 2:
                # The unit is the first in line
                unit_line.add_unit(unit)

            else:
                # The unit comes after another one
                # Search other_connections for the previous unit in line
                connected_types = connection.get_member("other_connections").get_value()
                connected_index = -1
                for index in range(len(connected_types)):
                    connected_type = connected_types[index].get_value()["other_connection"].get_value()
                    if connected_type == 2:
                        # 2 == Unit
                        connected_index = index
                        break

                else:
                    raise Exception("Unit %s is not first in line, but no previous unit can"
                                    " be found in other_connections" % (unit_id))

                # Find the id of the connected unit
                connected_ids = connection.get_member("other_connected_ids").get_value()
                previous_unit_id = connected_ids[connected_index].get_value()

                unit_line.add_unit(unit, after=previous_unit_id)

        # Store the lines in the data set with the head unit ids as keys
        for line in pre_unit_lines.values():
            full_data_set.unit_lines.update({line.get_head_unit_id(): line})

        # Store the lines in the data set with the line ids as keys
        full_data_set.unit_lines_vertical_ref.update(pre_unit_lines)

    @staticmethod
    def _create_extra_unit_lines(full_data_set):
        """
        Create additional units that are not in the unit connections.

        :param full_data_set: GenieObjectContainer instance that
                              contains all relevant data for the conversion
                              process.
        :type full_data_set: class: ...dataformat.aoc.genie_object_container.GenieObjectContainer
        """
        extra_units = (48, 65, 594, 833)  # Wildlife

        for unit_id in extra_units:
            unit_line = GenieUnitLineGroup(unit_id, full_data_set)
            unit_line.add_unit(full_data_set.genie_units[unit_id])
            full_data_set.unit_lines.update({unit_line.get_id(): unit_line})
            full_data_set.unit_ref.update({unit_id: unit_line})

    @staticmethod
    def _create_building_lines(full_data_set):
        """
        Establish building lines, based on information in the building connections.
        Because of how Genie building lines work, this will only find the first
        building in the line. Subsequent buildings in the line have to be determined
        by effects in AgeUpTechs.

        :param full_data_set: GenieObjectContainer instance that
                              contains all relevant data for the conversion
                              process.
        :type full_data_set: class: ...dataformat.aoc.genie_object_container.GenieObjectContainer
        """
        building_connections = full_data_set.building_connections

        for connection in building_connections.values():
            building_id = connection.get_member("id").get_value()
            building = full_data_set.genie_units[building_id]
            previous_building_id = None
            stack_building = False

            # Buildings have no actual lines, so we use
            # their unit ID as the line ID.
            line_id = building_id

            # Check if we have to create a GenieStackBuildingGroup
            if building.has_member("stack_unit_id") and \
                    building.get_member("stack_unit_id").get_value() > -1:
                stack_building = True

            if building.has_member("head_unit_id") and \
                    building.get_member("head_unit_id").get_value() > -1:
                # we don't care about head units because we process
                # them with their stack unit
                continue

            # Check if the building is part of an existing line.
            # To do this, we look for connected techs and
            # check if any tech has an upgrade effect.
            connected_types = connection.get_member("other_connections").get_value()
            connected_tech_indices = []
            for index in range(len(connected_types)):
                connected_type = connected_types[index].get_value()["other_connection"].get_value()
                if connected_type == 3:
                    # 3 == Tech
                    connected_tech_indices.append(index)

            connected_ids = connection.get_member("other_connected_ids").get_value()

            for index in connected_tech_indices:
                connected_tech_id = connected_ids[index].get_value()
                connected_tech = full_data_set.genie_techs[connected_tech_id]
                effect_bundle_id = connected_tech.get_member("tech_effect_id").get_value()
                effect_bundle = full_data_set.genie_effect_bundles[effect_bundle_id]

                upgrade_effects = effect_bundle.get_effects(effect_type=3)

                if len(upgrade_effects) < 0:
                    continue

                # Search upgrade effects for the line_id
                for upgrade in upgrade_effects:
                    upgrade_source = upgrade.get_member("attr_a").get_value()
                    upgrade_target = upgrade.get_member("attr_b").get_value()

                    # Check if the upgrade target is correct
                    if upgrade_target == building_id:
                        # Line id is the source building id
                        line_id = upgrade_source
                        break

                else:
                    # If no upgrade was found, then search remaining techs
                    continue

                # Find the previous building
                connected_index = -1
                for c_index in range(len(connected_types)):
                    connected_type = connected_types[c_index].get_value()["other_connection"].get_value()
                    if connected_type == 1:
                        # 1 == Building
                        connected_index = c_index
                        break

                else:
                    raise Exception("Building %s is not first in line, but no previous building can"
                                    " be found in other_connections" % (building_id))

                previous_building_id = connected_ids[connected_index].get_value()

                # Add the upgrade tech group to the data set.
                building_upgrade = BuildingLineUpgrade(connected_tech_id, line_id,
                                                       building_id, full_data_set)
                full_data_set.tech_groups.update({building_upgrade.get_id(): building_upgrade})
                full_data_set.building_upgrades.update({building_upgrade.get_id(): building_upgrade})

                break

            # Check if a line object already exists for this id
            # if not, create it
            if line_id in full_data_set.building_lines.keys():
                building_line = full_data_set.building_lines[line_id]
                building_line.add_unit(building, after=previous_building_id)
                full_data_set.unit_ref.update({building_id: building_line})

            else:
                if stack_building:
                    stack_unit_id = building.get_member("stack_unit_id").get_value()
                    building_line = GenieStackBuildingGroup(stack_unit_id, line_id, full_data_set)

                else:
                    building_line = GenieBuildingLineGroup(line_id, full_data_set)

                full_data_set.building_lines.update({building_line.get_id(): building_line})
                building_line.add_unit(building, after=previous_building_id)
                full_data_set.unit_ref.update({building_id: building_line})

    @staticmethod
    def _sanitize_effect_bundles(full_data_set):
        """
        Remove garbage data from effect bundles.

        :param full_data_set: GenieObjectContainer instance that
                              contains all relevant data for the conversion
                              process.
        :type full_data_set: class: ...dataformat.aoc.genie_object_container.GenieObjectContainer
        """
        effect_bundles = full_data_set.genie_effect_bundles

        for bundle in effect_bundles.values():
            sanitized_effects = {}

            effects = bundle.get_effects()

            index = 0
            for effect in effects:
                effect_type = effect.get_member("type_id").get_value()
                if effect_type < 0:
                    # Effect has no type
                    continue

                elif effect_type == 102:
                    if effect.get_member("attr_d").get_value() < 0:
                        # Tech disable effect with no tech id specified
                        continue

                sanitized_effects.update({index: effect})
                index += 1

            bundle.effects = sanitized_effects
            bundle.sanitized = True

    @staticmethod
    def _create_tech_groups(full_data_set):
        """
        Create economy techs from tech connections and unit upgrades/unlocks
        from unit connections.

        :param full_data_set: GenieObjectContainer instance that
                              contains all relevant data for the conversion
                              process.
        :type full_data_set: class: ...dataformat.aoc.genie_object_container.GenieObjectContainer
        """
        tech_connections = full_data_set.tech_connections

        for connection in tech_connections.values():
            connected_buildings = connection.get_member("buildings").get_value()
            tech_id = connection.get_member("id").get_value()
            tech = full_data_set.genie_techs[tech_id]

            # Check if the tech is an age upgrade
            if (tech.has_member("tech_type") and tech.get_member("tech_type").get_value() == 2)\
                    or connection.get_member("line_mode").get_value() == 0:
                # Search other_connections for the age id
                connected_types = connection.get_member("other_connections").get_value()
                connected_index = -1
                for index in range(len(connected_types)):
                    connected_type = connected_types[index].get_value()["other_connection"].get_value()
                    if connected_type == 0:
                        # 2 == Unit
                        connected_index = index
                        break

                else:
                    raise Exception("Tech %s is shown in Age progress bar, but no age id"
                                    " can be found in other_connections" % (tech_id))

                # Find the age id in the connected ids
                connected_ids = connection.get_member("other_connected_ids").get_value()
                age_id = connected_ids[connected_index].get_value()
                age_up = AgeUpgrade(tech_id, age_id, full_data_set)
                full_data_set.tech_groups.update({age_up.get_id(): age_up})
                full_data_set.age_upgrades.update({age_up.get_id(): age_up})

            elif len(connected_buildings) > 0:
                # Building upgrades are created in _create_building_lines() method
                # so we don't need to create them here
                if tech_id not in full_data_set.building_upgrades.keys():
                    # Check if the tech is a building unlock
                    effect_bundle_id = tech.get_member("tech_effect_id").get_value()
                    effect_bundle = full_data_set.genie_effect_bundles[effect_bundle_id]

                    unlock_effects = effect_bundle.get_effects(effect_type=2)

                    if len(unlock_effects) > 0:
                        # Search unlock effects for the line_id
                        for upgrade in unlock_effects:
                            unlock_id = upgrade.get_member("attr_a").get_value()

                        building_unlock = BuildingUnlock(tech_id, unlock_id, full_data_set)
                        full_data_set.tech_groups.update({building_unlock.get_id(): building_unlock})
                        full_data_set.building_unlocks.update({building_unlock.get_id(): building_unlock})

            else:
                # Create a stat upgrade for other techs
                stat_up = StatUpgrade(tech_id, full_data_set)
                full_data_set.tech_groups.update({stat_up.get_id(): stat_up})
                full_data_set.stat_upgrades.update({stat_up.get_id(): stat_up})

        # Unit upgrades and unlocks are stored in unit connections
        unit_connections = full_data_set.unit_connections

        for connection in unit_connections.values():
            unit_id = connection.get_member("id").get_value()
            required_research_id = connection.get_member("required_research").get_value()
            enabling_research_id = connection.get_member("enabling_research").get_value()
            line_mode = connection.get_member("line_mode").get_value()
            line_id = connection.get_member("vertical_line").get_value()

            if required_research_id == -1 and enabling_research_id == -1:
                # Unit is unlocked from the start
                continue

            elif line_mode == 2:
                # Unit is first in line, there should be an unlock tech
                unit_unlock = UnitUnlock(enabling_research_id, line_id, full_data_set)
                full_data_set.tech_groups.update({unit_unlock.get_id(): unit_unlock})
                full_data_set.unit_unlocks.update({unit_unlock.get_id(): unit_unlock})

            elif line_mode == 3:
                # Units further down the line receive line upgrades
                unit_upgrade = UnitLineUpgrade(required_research_id, line_id,
                                               unit_id, full_data_set)
                full_data_set.tech_groups.update({unit_upgrade.get_id(): unit_upgrade})
                full_data_set.unit_upgrades.update({unit_upgrade.get_id(): unit_upgrade})

        # Initiated techs are stored with buildings
        genie_units = full_data_set.genie_units

        for genie_unit in genie_units.values():
            if not genie_unit.has_member("research_id"):
                continue

            building_id = genie_unit.get_member("id0").get_value()
            initiated_tech_id = genie_unit.get_member("research_id").get_value()

            if initiated_tech_id == -1:
                continue

            initiated_tech = InitiatedTech(initiated_tech_id, building_id, full_data_set)
            full_data_set.tech_groups.update({initiated_tech.get_id(): initiated_tech})
            full_data_set.initiated_techs.update({initiated_tech.get_id(): initiated_tech})

        # Civ boni have to be aquired from techs
        # Civ boni = ONLY passive boni (not unit unlocks, unit upgrades or team bonus)
        genie_techs = full_data_set.genie_techs

        for index in range(len(genie_techs)):
            tech_id = index

            # Civ ID must be positive and non-zero
            civ_id = genie_techs[index].get_member("civilization_id").get_value()
            if civ_id <= 0:
                continue

            # Passive boni are not researched anywhere
            research_location_id = genie_techs[index].get_member("research_location_id").get_value()
            if research_location_id > 0:
                continue

            # Passive boni are not available in full tech mode
            full_tech_mode = genie_techs[index].get_member("full_tech_mode").get_value()
            if full_tech_mode:
                continue

            civ_bonus = CivBonus(tech_id, civ_id, full_data_set)
            full_data_set.tech_groups.update({civ_bonus.get_id(): civ_bonus})
            full_data_set.civ_boni.update({civ_bonus.get_id(): civ_bonus})

    @staticmethod
    def _create_civ_groups(full_data_set):
        """
        Create civilization groups from civ objects.

        :param full_data_set: GenieObjectContainer instance that
                              contains all relevant data for the conversion
                              process.
        :type full_data_set: class: ...dataformat.aoc.genie_object_container.GenieObjectContainer
        """
        civ_objects = full_data_set.genie_civs

        for index in range(len(civ_objects)):
            civ_id = index

            civ_group = GenieCivilizationGroup(civ_id, full_data_set)
            full_data_set.civ_groups.update({civ_group.get_id(): civ_group})

            index += 1

    @staticmethod
    def _create_villager_groups(full_data_set):
        """
        Create task groups and assign the relevant male and female group to a
        villager group.

        :param full_data_set: GenieObjectContainer instance that
                              contains all relevant data for the conversion
                              process.
        :type full_data_set: class: ...dataformat.aoc.genie_object_container.GenieObjectContainer
        """
        units = full_data_set.genie_units
        task_group_ids = set()
        unit_ids = set()

        # Find task groups in the dataset
        for unit in units.values():
            if unit.has_member("task_group"):
                task_group_id = unit.get_member("task_group").get_value()

            else:
                task_group_id = 0

            if task_group_id == 0:
                # no task group
                continue

            if task_group_id in task_group_ids:
                task_group = full_data_set.task_groups[task_group_id]
                task_group.add_unit(unit)

            else:
                if task_group_id == 1:
                    line_id = GenieUnitTaskGroup.male_line_id

                elif task_group_id == 2:
                    line_id = GenieUnitTaskGroup.female_line_id

                task_group = GenieUnitTaskGroup(line_id, task_group_id, full_data_set)
                task_group.add_unit(unit)
                full_data_set.task_groups.update({task_group_id: task_group})

            task_group_ids.add(task_group_id)
            unit_ids.add(unit.get_member("id0").get_value())

        # Create the villager task group
        villager = GenieVillagerGroup(118, task_group_ids, full_data_set)
        full_data_set.unit_lines.update({villager.get_id(): villager})
        full_data_set.villager_groups.update({villager.get_id(): villager})
        for unit_id in unit_ids:
            full_data_set.unit_ref.update({unit_id: villager})

    @staticmethod
    def _create_ambient_groups(full_data_set):
        """
        Create ambient groups, mostly for resources and scenery.

        :param full_data_set: GenieObjectContainer instance that
                              contains all relevant data for the conversion
                              process.
        :type full_data_set: class: ...dataformat.aoc.genie_object_container.GenieObjectContainer
        """
        ambient_ids = AMBIENT_GROUP_LOOKUPS.keys()
        genie_units = full_data_set.genie_units

        for ambient_id in ambient_ids:
            ambient_group = GenieAmbientGroup(ambient_id, full_data_set)
            ambient_group.add_unit(genie_units[ambient_id])
            full_data_set.ambient_groups.update({ambient_group.get_id(): ambient_group})
            full_data_set.unit_ref.update({ambient_id: ambient_group})

    @staticmethod
    def _create_variant_groups(full_data_set):
        """
        Create variant groups.

        :param full_data_set: GenieObjectContainer instance that
                              contains all relevant data for the conversion
                              process.
        :type full_data_set: class: ...dataformat.aoc.genie_object_container.GenieObjectContainer
        """
        variants = VARIANT_GROUP_LOOKUPS

        for group_id, variant in variants.items():
            variant_group = GenieVariantGroup(group_id, full_data_set)
            full_data_set.variant_groups.update({variant_group.get_id(): variant_group})

            for variant_id in variant[2]:
                variant_group.add_unit(full_data_set.genie_units[variant_id])
                full_data_set.unit_ref.update({variant_id: variant_group})

    @staticmethod
    def _create_terrain_groups(full_data_set):
        """
        Create terrain groups.

        :param full_data_set: GenieObjectContainer instance that
                              contains all relevant data for the conversion
                              process.
        :type full_data_set: class: ...dataformat.aoc.genie_object_container.GenieObjectContainer
        """
        terrains = full_data_set.genie_terrains.values()

        for terrain in terrains:
            enabled = terrain.get_member("enabled").get_value()

            if enabled:
                terrain_group = GenieTerrainGroup(terrain.get_id(), full_data_set)
                full_data_set.terrain_groups.update({terrain.get_id(): terrain_group})

    @staticmethod
    def _link_building_upgrades(full_data_set):
        """
        Find building upgrades in the AgeUp techs and append them to the building lines.

        :param full_data_set: GenieObjectContainer instance that
                              contains all relevant data for the conversion
                              process.
        :type full_data_set: class: ...dataformat.aoc.genie_object_container.GenieObjectContainer
        """
        age_ups = full_data_set.age_upgrades

        # Order of age ups should be correct
        for age_up in age_ups.values():
            for effect in age_up.effects.get_effects():
                type_id = effect.get_type()

                if type_id != 3:
                    continue

                upgrade_source_id = effect["attr_a"].get_value()
                upgrade_target_id = effect["attr_b"].get_value()

                if upgrade_source_id not in full_data_set.building_lines.keys():
                    continue

                upgraded_line = full_data_set.building_lines[upgrade_source_id]
                upgrade_target = full_data_set.genie_units[upgrade_target_id]

                upgraded_line.add_unit(upgrade_target)
                full_data_set.unit_ref.update({upgrade_target_id: upgraded_line})

    @staticmethod
    def _link_creatables(full_data_set):
        """
        Link creatable units and buildings to their creating entity. This is done
        to provide quick access during conversion.

        :param full_data_set: GenieObjectContainer instance that
                              contains all relevant data for the conversion
                              process.
        :type full_data_set: class: ...dataformat.aoc.genie_object_container.GenieObjectContainer
        """
        # Link units to buildings
        unit_lines = full_data_set.unit_lines

        for unit_line in unit_lines.values():
            if unit_line.is_creatable():
                train_location_id = unit_line.get_train_location_id()
                full_data_set.building_lines[train_location_id].add_creatable(unit_line)

        # Link buildings to villagers and fishing ships
        building_lines = full_data_set.building_lines

        for building_line in building_lines.values():
            if building_line.is_creatable():
                train_location_id = building_line.get_train_location_id()

                if train_location_id in full_data_set.villager_groups.keys():
                    full_data_set.villager_groups[train_location_id].add_creatable(building_line)

                else:
                    # try normal units
                    full_data_set.unit_lines[train_location_id].add_creatable(building_line)

    @staticmethod
    def _link_researchables(full_data_set):
        """
        Link techs to their buildings. This is done
        to provide quick access during conversion.

        :param full_data_set: GenieObjectContainer instance that
                              contains all relevant data for the conversion
                              process.
        :type full_data_set: class: ...dataformat.aoc.genie_object_container.GenieObjectContainer
        """
        tech_groups = full_data_set.tech_groups

        for tech in tech_groups.values():
            if tech.is_researchable():
                research_location_id = tech.get_research_location_id()
                full_data_set.building_lines[research_location_id].add_researchable(tech)

    @staticmethod
    def _link_civ_uniques(full_data_set):
        """
        Link civ bonus techs, unique units and unique techs to their civs.

        :param full_data_set: GenieObjectContainer instance that
                              contains all relevant data for the conversion
                              process.
        :type full_data_set: class: ...dataformat.aoc.genie_object_container.GenieObjectContainer
        """
        for bonus in full_data_set.civ_boni.values():
            civ_id = bonus.get_civilization()
            full_data_set.civ_groups[civ_id].add_civ_bonus(bonus)

        for unit_line in full_data_set.unit_lines.values():
            if unit_line.is_unique():
                head_unit_id = unit_line.get_head_unit_id()
                head_unit_connection = full_data_set.unit_connections[head_unit_id]
                enabling_research_id = head_unit_connection.get_member("enabling_research").get_value()
                enabling_research = full_data_set.genie_techs[enabling_research_id]
                enabling_civ_id = enabling_research.get_member("civilization_id").get_value()

                full_data_set.civ_groups[enabling_civ_id].add_unique_entity(unit_line)

        for building_line in full_data_set.building_lines.values():
            if building_line.is_unique():
                head_unit_id = building_line.get_head_unit_id()
                head_building_connection = full_data_set.building_connections[head_unit_id]
                enabling_research_id = head_building_connection.get_member("enabling_research").get_value()
                enabling_research = full_data_set.genie_techs[enabling_research_id]
                enabling_civ_id = enabling_research.get_member("civilization_id").get_value()

                full_data_set.civ_groups[enabling_civ_id].add_unique_entity(building_line)

        for tech_group in full_data_set.tech_groups.values():
            if tech_group.is_unique() and tech_group.is_researchable():
                civ_id = tech_group.get_civilization()
                full_data_set.civ_groups[civ_id].add_unique_tech(tech_group)

    @staticmethod
    def _link_resources_to_dropsites(full_data_set):
        """
        Link resources to the buildings they can be dropped off at. This is done
        to provide quick access during conversion.

        :param full_data_set: GenieObjectContainer instance that
                              contains all relevant data for the conversion
                              process.
        :type full_data_set: class: ...dataformat.aoc.genie_object_container.GenieObjectContainer
        """
        villager_groups = full_data_set.villager_groups

        for villager in villager_groups.values():
            for variant in villager.variants:
                for unit in variant.line:
                    drop_site_id0 = unit.get_member("drop_site0").get_value()
                    drop_site_id1 = unit.get_member("drop_site1").get_value()

                    if drop_site_id0 > -1:
                        drop_site0 = full_data_set.building_lines[drop_site_id0]

                    if drop_site_id1 > -1:
                        drop_site1 = full_data_set.building_lines[drop_site_id1]

                    commands = unit.get_member("unit_commands").get_value()
                    for command in commands:
                        type_id = command.get_value()["type"].get_value()

                        if type_id in (5, 110):
                            resource_id = command.get_value()["resource_out"].get_value()

                            if resource_id == -1:
                                resource_id = command.get_value()["resource_in"].get_value()

                            if drop_site_id0 > -1:
                                drop_site0.add_accepted_resource(resource_id)
                            if drop_site_id1 > -1:
                                drop_site1.add_accepted_resource(resource_id)

    @staticmethod
    def _link_garrison(full_data_set):
        """
        Link a garrison unit to the lines that are stored and vice versa. This is done
        to provide quick access during conversion.

        :param full_data_set: GenieObjectContainer instance that
                              contains all relevant data for the conversion
                              process.
        :type full_data_set: class: ...dataformat.aoc.genie_object_container.GenieObjectContainer
        """
        unit_lines = full_data_set.unit_lines
        building_lines = full_data_set.building_lines
        ambient_groups = full_data_set.ambient_groups

        garrison_lines = {}
        garrison_lines.update(unit_lines)
        garrison_lines.update(building_lines)

        for garrison in garrison_lines.values():
            if garrison.is_garrison():
                garrison_mode = garrison.get_garrison_mode()
                garrison_head = garrison.get_head_unit()
                garrison_type = 0

                if garrison.get_garrison_mode() == GenieGarrisonMode.NATURAL:
                    garrison_type = garrison_head.get_member("garrison_type").get_value()

                # Check all lines if they fit the garrison mode
                for unit_line in unit_lines.values():
                    head_unit = unit_line.get_head_unit()
                    creatable_type = head_unit.get_member("creatable_type").get_value()
                    trait = head_unit.get_member("trait").get_value()

                    if creatable_type not in garrison_mode.value:
                        # Exception for ships; instead handled below
                        if not trait & 0x02:
                            continue

                    if garrison_mode == GenieGarrisonMode.NATURAL:
                        if creatable_type == 1 and not garrison_type & 0x01:
                            continue

                        elif creatable_type == 2 and not garrison_type & 0x02:
                            continue

                        elif creatable_type == 2 and unit_line.get_class_id() in (13, 51, 54, 55):
                            # Siege and trebuchet cannot be in garrisons
                            # even though the .dat file allows them to
                            continue

                        elif creatable_type == 3 and not garrison_type & 0x04:
                            continue

                        elif creatable_type == 6 and not garrison_type & 0x08:
                            continue

                    # Prevents siege units/trebuchet from being stored in rams
                    if garrison_mode == GenieGarrisonMode.UNIT_GARRISON:
                        if unit_line.get_class_id() in (13, 51, 54, 55):
                            continue

                    if garrison_mode == GenieGarrisonMode.SELF_PRODUCED:
                        if not unit_line in garrison.creates:
                            continue

                    # Allow ships as garrisoned units, but only for production
                    if trait & 0x02 and not garrison_mode == GenieGarrisonMode.SELF_PRODUCED:
                        continue

                    unit_line.garrison_locations.append(garrison)
                    garrison.garrison_entities.append(unit_line)

                if garrison_mode == GenieGarrisonMode.MONK:
                    # Search for the relic
                    for ambient_group in ambient_groups.values():
                        head_unit = ambient_group.get_head_unit()
                        if not head_unit.has_member("creatable_type"):
                            continue

                        creatable_type = head_unit.get_member("creatable_type").get_value()
                        if creatable_type != 4:
                            continue

                        ambient_group.garrison_locations.append(garrison)
                        garrison.garrison_entities.append(ambient_group)

    @staticmethod
    def _link_trade_posts(full_data_set):
        """
        Link a trade post building to the lines that it trades with.

        :param full_data_set: GenieObjectContainer instance that
                              contains all relevant data for the conversion
                              process.
        :type full_data_set: class: ...dataformat.aoc.genie_object_container.GenieObjectContainer
        """
        unit_lines = full_data_set.unit_lines.values()

        for unit_line in unit_lines:
            if unit_line.has_command(111):
                head_unit = unit_line.get_head_unit()
                unit_commands = head_unit.get_member("unit_commands").get_value()
                trade_post_id = -1
                for command in unit_commands:
                    # Find the trade command and the trade post id
                    type_id = command.get_value()["type"].get_value()

                    if type_id != 111:
                        continue

                    trade_post_id = command.get_value()["unit_id"].get_value()
                    break

                # Notify buiding
                full_data_set.building_lines[trade_post_id].add_trading_line(unit_line)
