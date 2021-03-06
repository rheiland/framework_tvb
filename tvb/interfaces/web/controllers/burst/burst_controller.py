# -*- coding: utf-8 -*-
#
#
# TheVirtualBrain-Framework Package. This package holds all Data Management, and 
# Web-UI helpful to run brain-simulations. To use it, you also need do download
# TheVirtualBrain-Scientific Package (for simulators). See content of the
# documentation-folder for more details. See also http://www.thevirtualbrain.org
#
# (c) 2012-2013, Baycrest Centre for Geriatric Care ("Baycrest")
#
# This program is free software; you can redistribute it and/or modify it under 
# the terms of the GNU General Public License version 2 as published by the Free
# Software Foundation. This program is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public
# License for more details. You should have received a copy of the GNU General 
# Public License along with this program; if not, you can download it here
# http://www.gnu.org/licenses/old-licenses/gpl-2.0
#
#
#   CITATION:
# When using The Virtual Brain for scientific publications, please cite it as follows:
#
#   Paula Sanz Leon, Stuart A. Knock, M. Marmaduke Woodman, Lia Domide,
#   Jochen Mersmann, Anthony R. McIntosh, Viktor Jirsa (2013)
#       The Virtual Brain: a simulator of primate brain network dynamics.
#   Frontiers in Neuroinformatics (7:10. doi: 10.3389/fninf.2013.00010)
#
#
"""
Control code for Main-Burst Page.

.. moduleauthor:: Lia Domide <lia.domide@codemart.ro>
.. moduleauthor:: Bogdan Neacsa <bogdan.neacsa@codemart.ro>
"""

import json
import copy
import cherrypy
import formencode
from formencode import validators
from tvb.config import SIMULATOR_MODULE, SIMULATOR_CLASS, MEASURE_METRICS_MODULE, MEASURE_METRICS_CLASS
from tvb.basic.config.settings import TVBSettings as cfg
from tvb.core.utils import generate_guid
from tvb.core.adapters.abcadapter import ABCAdapter
from tvb.core.services.burst_service import BurstService, KEY_PARAMETER_CHECKED
from tvb.core.services.workflow_service import WorkflowService
from tvb.core.services.operation_service import RANGE_PARAMETER_1, RANGE_PARAMETER_2
import tvb.interfaces.web.controllers.base_controller as base
from tvb.interfaces.web.controllers.users_controller import logged
from tvb.interfaces.web.controllers.base_controller import using_template, ajax_call
from tvb.interfaces.web.controllers.flow_controller import context_selected, KEY_CONTROLLS, SelectedAdapterContext

PORTLET_STEP_SEPARATOR = "____"
BURST_NAME = 'burstName'



class BurstController(base.BaseController):
    """
    Controller class for Burst-Pages.
    """


    def __init__(self):
        base.BaseController.__init__(self)
        self.burst_service = BurstService()
        self.workflow_service = WorkflowService()
        self.context = SelectedAdapterContext()

        ## Cache simulator Tree, Algorithm and AlgorithmGroup, for performance issues.
        algorithm, self.cached_simulator_algo_group = self.flow_service.get_algorithm_by_module_and_class(
            SIMULATOR_MODULE, SIMULATOR_CLASS)
        self.cached_simulator_algorithm_id = algorithm.id


    @property
    @context_selected()
    def cached_simulator_input_tree(self):
        """
        Cache Simulator's input tree, for performance issues.
        Anyway, without restart, the introspected tree will not be different on multiple executions.
        :returns: Simulator's Input Tree (copy from cache or just loaded)
        """
        cached_simulator_tree = base.get_from_session(base.KEY_CACHED_SIMULATOR_TREE)
        if cached_simulator_tree is None:
            cached_simulator_tree = self.flow_service.prepare_adapter(base.get_current_project().id,
                                                                      self.cached_simulator_algo_group)[1]
            base.add2session(base.KEY_CACHED_SIMULATOR_TREE, cached_simulator_tree)
        return copy.deepcopy(cached_simulator_tree)


    @cherrypy.expose
    @using_template('base_template')
    @base.settings()
    @logged()
    @context_selected()
    def index(self):
        """Get on burst main page"""
        template_specification = dict(mainContent="burst/main_burst", title="Simulation Cockpit",
                                      baseUrl=cfg.BASE_URL, includedResources='project/included_resources')
        portlets_list = self.burst_service.get_available_portlets()
        session_stored_burst = base.get_from_session(base.KEY_BURST_CONFIG)
        if session_stored_burst is None or session_stored_burst.id is None:
            if session_stored_burst is None:
                session_stored_burst = self.burst_service.new_burst_configuration(base.get_current_project().id)
                base.add2session(base.KEY_BURST_CONFIG, session_stored_burst)

            adapter_interface = self.cached_simulator_input_tree
            if session_stored_burst is not None:
                current_data = session_stored_burst.get_all_simulator_values()[0]
                adapter_interface = ABCAdapter.fill_defaults(adapter_interface, current_data, True)
                ### Add simulator tree to session to be available in filters
                self.context.add_adapter_to_session(self.cached_simulator_algo_group, adapter_interface, current_data)
            template_specification['inputList'] = adapter_interface

        selected_portlets = session_stored_burst.update_selected_portlets()
        template_specification['burst_list'] = self.burst_service.get_available_bursts(base.get_current_project().id)
        template_specification['portletList'] = portlets_list
        template_specification['selectedPortlets'] = json.dumps(selected_portlets)
        template_specification['draw_hidden_ranges'] = True
        template_specification['burstConfig'] = session_stored_burst

        ### Prepare PSE available metrics
        ### We put here all available algorithms, because the metrics select area is a generic one, 
        ### and not loaded with every Burst Group change in history.
        algo_group = self.flow_service.get_algorithm_by_module_and_class(MEASURE_METRICS_MODULE,
                                                                         MEASURE_METRICS_CLASS)[1]
        adapter_instance = ABCAdapter.build_adapter(algo_group)
        if adapter_instance is not None and hasattr(adapter_instance, 'available_algorithms'):
            template_specification['available_metrics'] = [metric_name for metric_name
                                                           in adapter_instance.available_algorithms.keys()]
        else:
            template_specification['available_metrics'] = []

        template_specification[base.KEY_PARAMETERS_CONFIG] = False
        template_specification[base.KEY_SECTION] = 'burst'
        return self.fill_default_attributes(template_specification)


    @cherrypy.expose
    @using_template('burst/burst_history')
    def load_burst_history(self):
        """
        Load the available burst that are stored in the database at this time.
        This is one alternative to 'chrome-back problem'.
        """
        session_burst = base.get_from_session(base.KEY_BURST_CONFIG)
        return {'burst_list': self.burst_service.get_available_bursts(base.get_current_project().id),
                'selectedBurst': session_burst.id}


    @cherrypy.expose
    @ajax_call(False)
    def get_selected_burst(self):
        """
        Return the burst that is currently stored in session.
        This is one alternative to 'chrome-back problem'.
        """
        session_burst = base.get_from_session(base.KEY_BURST_CONFIG)
        if session_burst.id:
            return str(session_burst.id)
        else:
            return 'None'


    @cherrypy.expose
    @using_template('burst/portlet_configure_parameters')
    def get_portlet_configurable_interface(self, index_in_tab):
        """
        From the position given by the tab index and the index from that tab, 
        get the portlet configuration and build the configurable interface
        for that portlet.
        """
        burst_config = base.get_from_session(base.KEY_BURST_CONFIG)
        tab_index = burst_config.selected_tab
        portlet_config = burst_config.tabs[tab_index].portlets[int(index_in_tab)]
        portlet_interface = self.burst_service.build_portlet_interface(portlet_config, base.get_current_project().id)

        full_portlet_input_tree = []
        for entry in portlet_interface:
            full_portlet_input_tree.extend(entry.interface)
        self.context.add_portlet_to_session(full_portlet_input_tree)

        portlet_interface = {"adapters_list": portlet_interface,
                             base.KEY_PARAMETERS_CONFIG: False,
                             base.KEY_SESSION_TREE: self.context.KEY_PORTLET_CONFIGURATION}
        return self.fill_default_attributes(portlet_interface)


    @cherrypy.expose
    @using_template('burst/portlets_preview')
    def portlet_tab_display(self, **data):
        """
        When saving a new configuration of tabs, check if any of the old 
        portlets are still present, and if that is the case use their 
        parameters configuration. 
        
        For all the new portlets add entries in the burst configuration. 
        Also remove old portlets that are no longer saved.
        """
        tab_portlets_list = json.loads(data['tab_portlets_list'])
        burst_config = base.get_from_session(base.KEY_BURST_CONFIG)
        selected_tab_idx = burst_config.selected_tab
        for tab_idx in xrange(len(tab_portlets_list)):
            current_tab = burst_config.tabs[tab_idx]
            ### When configuration already exists, and new portlets          #####
            ### are selected, first check if any configuration was saved for #####
            ### each portlet and if that is the case, use it. If none is present #
            ### create a new one.                                              ###
            for idx_in_tab in xrange(len(tab_portlets_list[tab_idx])):
                portlet_id = tab_portlets_list[tab_idx][idx_in_tab][0]
                portlet_name = tab_portlets_list[tab_idx][idx_in_tab][1]
                if portlet_id >= 0:
                    saved_config = current_tab.portlets[idx_in_tab]
                    if saved_config is None or saved_config.portlet_id != portlet_id:
                        current_tab.portlets[idx_in_tab] = self.burst_service.new_portlet_configuration(portlet_id,
                                                                                    tab_idx, idx_in_tab, portlet_name)
                    else:
                        saved_config.visualizer.ui_name = portlet_name
                else:
                    current_tab.portlets[idx_in_tab] = None
            #For generating the HTML get for each id the corresponding portlet
        selected_tab_portlets = []
        saved_selected_tab = burst_config.tabs[selected_tab_idx]
        for portlet in saved_selected_tab.portlets:
            if portlet:
                portlet_id = int(portlet.portlet_id)
                portlet_entity = self.burst_service.get_portlet_by_id(portlet_id)
                portlet_entity.name = portlet.name
                selected_tab_portlets.append(portlet_entity)

        return {'portlet_tab_list': selected_tab_portlets}


    @cherrypy.expose
    @using_template('burst/portlets_preview')
    def get_configured_portlets(self):
        """
        Return the portlets for one given tab. This is used when changing
        from tab to tab and selecting which portlets will be displayed.
        """
        burst_config = base.get_from_session(base.KEY_BURST_CONFIG)
        if burst_config is None:
            return {'portlet_tab_list': []}

        tab_idx = burst_config.selected_tab
        tab_portlet_list = []
        for portlet_cfg in burst_config.tabs[int(tab_idx)].portlets:
            if portlet_cfg is not None:
                portlet_entity = self.burst_service.get_portlet_by_id(portlet_cfg.portlet_id)
                portlet_entity.name = portlet_cfg.name
                tab_portlet_list.append(portlet_entity)
        return {'portlet_tab_list': tab_portlet_list}


    @cherrypy.expose
    @ajax_call()
    def change_selected_tab(self, tab_nr):
        """
        Set :param tab_nr: as the currently selected tab in the stored burst
        configuration. 
        """
        base.get_from_session(base.KEY_BURST_CONFIG).selected_tab = int(tab_nr)


    @cherrypy.expose
    @ajax_call()
    def get_portlet_session_configuration(self):
        """
        Get the current configuration of portlets stored in session for this burst,
        as a json.
        """
        burst_entity = base.get_from_session(base.KEY_BURST_CONFIG)
        returned_configuration = burst_entity.update_selected_portlets()
        return returned_configuration


    @cherrypy.expose
    @ajax_call(False)
    def save_parameters(self, index_in_tab, **data):
        """
        Save parameters
        
        :param tab_nr: the index of the selected tab
        :param index_in_tab: the index of the configured portlet in the selected tab
        :param data: the {name:value} dictionary configuration of the current portlet
        
        Having these inputs, update the configuration of the portletin the 
        corresponding tab position form the burst configuration .
        """
        burst_config = base.get_from_session(base.KEY_BURST_CONFIG)
        tab_nr = burst_config.selected_tab
        old_portlet_config = burst_config.tabs[int(tab_nr)].portlets[int(index_in_tab)]

        # Replace all void entries with 'None'
        for entry in data:
            if data[entry] == '':
                data[entry] = None

        need_relaunch = self.burst_service.update_portlet_configuration(old_portlet_config, data)
        if need_relaunch:
            #### Reset Burst Configuration into an entity not persisted (id = None for all)
            base.add2session(base.KEY_BURST_CONFIG, burst_config.clone())
            return "relaunchView"
        else:
            self.workflow_service.store_workflow_step(old_portlet_config.visualizer)
            return "noRelaunch"


    @cherrypy.expose
    @ajax_call()
    def rename_burst(self, burst_id, burst_name):
        """
        Rename the burst given by burst_id, setting it's new name to
        burst_name.
        """
        self._validate_burst_name(burst_name)
        self.burst_service.rename_burst(burst_id, burst_name)


    @cherrypy.expose
    @ajax_call()
    def launch_burst(self, launch_mode, burst_name, **data):
        """
        Do the actual burst launch, using the configuration saved in current session.
        :param launch_mode: new/branch/continue
        :param burst_name: user-given burst name. It can be empty (case in which we will fill with simulation_x)
        :param data: kwargs for simulation input parameters.
        """
        burst_config = base.get_from_session(base.KEY_BURST_CONFIG)

        ## Validate new burst-name
        if burst_name != 'none_undefined':
            self._validate_burst_name(burst_name)
            burst_config.name = burst_name

        ## Fill all parameters 
        user_id = base.get_logged_user().id
        data[base.KEY_ADAPTER] = self.cached_simulator_algorithm_id
        burst_config.update_simulator_configuration(data)
        burst_config.fk_project = base.get_current_project().id

        ## Do the asynchronous launch
        burst_id, burst_name = self.burst_service.launch_burst(burst_config, 0, self.cached_simulator_algorithm_id,
                                                               user_id, launch_mode)
        return [burst_id, burst_name]


    @cherrypy.expose
    @ajax_call()
    def load_burst(self, burst_id):
        """
        Given a clicked burst from the history and the selected tab, load all 
        the required data from that burst. Return a value specifying if it was a result
        of a range launch (OperationGroup) or not.
        """
        try:
            old_burst = base.get_from_session(base.KEY_BURST_CONFIG)
            burst, group_gid = self.burst_service.load_burst(burst_id)
            burst.selected_tab = old_burst.selected_tab
            base.add2session(base.KEY_BURST_CONFIG, burst)
            return {'status': burst.status, 'group_gid': group_gid, 'selected_tab': burst.selected_tab}
        except Exception, excep:
            ### Most probably Burst was removed. Delete it from session, so that client 
            ### has a good chance to get a good response on refresh
            self.logger.error(excep)
            base.remove_from_session(base.KEY_BURST_CONFIG)
            raise excep


    @cherrypy.expose
    @ajax_call()
    def get_history_status(self, **data):
        """
        For each burst id received, get the status and return it.
        """
        return self.burst_service.update_history_status(json.loads(data['burst_ids']))


    @cherrypy.expose
    @ajax_call(False)
    def cancel_or_remove_burst(self, burst_id):
        """
        Cancel or Remove the burst entity given by burst_id.
        :returns 'reset-new': When currently selected burst was removed. JS will need to reset selection to a new entry
        :returns 'canceled': When current burst was still running and was just stopped.
        :returns 'done': When no action is required on the client.
        """
        burst_id = int(burst_id)
        session_burst = base.get_from_session(base.KEY_BURST_CONFIG)
        removed = self.burst_service.cancel_or_remove_burst(burst_id)
        if removed:
            if session_burst.id == burst_id:
                return "reset-new"
            return 'done'
        else:
            # Burst was stopped since it was running
            return 'canceled'


    @cherrypy.expose
    @ajax_call()
    def get_selected_portlets(self):
        """
        Get the selected portlets for the loaded burst.
        """
        burst = base.get_from_session(base.KEY_BURST_CONFIG)
        return burst.update_selected_portlets()


    @cherrypy.expose
    @ajax_call(False)
    def get_visualizers_for_operation_id(self, op_id, width, height):
        """
        Method called from parameters exploration page in case a burst with a range of parameters
        for the simulator was launched. 
        :param op_id: the selected operation id from the parameter space exploration.
        :param width: the width of the right side display
        :param height: the height of the right side display
        
        Given these parameters first get the workflow to which op_id belongs, then load the portlets
        from that workflow as the current burst configuration. Width and height are used to get the
        proper sizes for the visualization iFrames. 
        """
        burst_config = base.get_from_session(base.KEY_BURST_CONFIG)
        burst_config = self.burst_service.load_tab_configuration(burst_config, op_id)
        base.add2session(base.KEY_BURST_CONFIG, burst_config)
        return self.load_configured_visualizers(width, height)


    @cherrypy.expose
    @using_template("burst/portlets_view")
    def load_configured_visualizers(self, width='800', height='600'):
        """
        Load all the visualization steps for this tab. Width and height represent
        the dimensions of the right side Div, so that we can compute for each iFrame
        the maximum size it's visualizer can take.
        """
        burst = base.get_from_session(base.KEY_BURST_CONFIG)
        selected_tab = burst.selected_tab
        tab_portlet_list = []
        for portlet_cfg in burst.tabs[int(selected_tab)].portlets:
            if portlet_cfg is not None:
                tab_portlet_list.append(self.__portlet_config2portlet_entity(portlet_cfg))
        return {'status': burst.status, 'portlet_tab_list': tab_portlet_list,
                'max_width': int(width), 'max_height': int(height)}


    @cherrypy.expose
    @using_template("burst/portlet_visualization_template")
    def check_status_for_visualizer(self, selected_tab, index_in_tab, width='800', height='600'):
        """
        This call is used to check on a regular basis if the data for a certain portlet is 
        available for visualization. Should return the status and the HTML to be displayed.
        """
        burst = base.get_from_session(base.KEY_BURST_CONFIG)
        target_portlet = burst.tabs[int(selected_tab)].portlets[int(index_in_tab)]
        target_portlet = self.__portlet_config2portlet_entity(target_portlet)
        template_dict = {'portlet_entity': target_portlet, 'width': int(width), 'height': int(height)}
        return template_dict


    @cherrypy.expose
    @ajax_call()
    def reset_burst(self):
        """
        Called when click on "New Burst" entry happens from UI.
        This will generate an empty new Burst Configuration.
        """
        base.remove_from_session(base.KEY_CACHED_SIMULATOR_TREE)
        new_burst = self.burst_service.new_burst_configuration(base.get_current_project().id)
        base.add2session(base.KEY_BURST_CONFIG, new_burst)


    @cherrypy.expose
    @ajax_call(False)
    def copy_burst(self, burst_id):
        """
        When currently selected entry is a valid Burst, create a clone of that Burst.
        """
        base.remove_from_session(base.KEY_CACHED_SIMULATOR_TREE)
        base_burst = self.burst_service.load_burst(burst_id)[0]
        if (base_burst is None) or (base_burst.id is None):
            return self.reset_burst()
        base.add2session(base.KEY_BURST_CONFIG, base_burst.clone())
        return base_burst.name


    @cherrypy.expose
    @using_template("burst/base_portlets_iframe")
    def launch_visualization(self, index_in_tab, frame_width, frame_height, method_name="generate_preview"):
        """
        Launch the visualization for this tab and index in tab. The width and height represent the maximum of the inner 
        visualization canvas so that it can fit in the iFrame.
        """
        result = {}
        try:
            burst = base.get_from_session(base.KEY_BURST_CONFIG)
            visualizer = burst.tabs[burst.selected_tab].portlets[int(index_in_tab)].visualizer
            result = self.burst_service.launch_visualization(visualizer, float(frame_width),
                                                             float(frame_height), method_name)[0]
            result['launch_success'] = True
        except Exception, ex:
            result['launch_success'] = False
            result['error_msg'] = str(ex)
        return result


    @cherrypy.expose
    @using_template("flow/genericAdapterFormFields")
    def configure_simulator_parameters(self):
        """
        Return the required input tree to generate the simulator interface for
        the burst page in 'configuration mode', meaning with checkboxes next to
        each input that are checked or not depending on if the user selected 
        them so, and with the user filled defaults.
        """
        burst_config = base.get_from_session(base.KEY_BURST_CONFIG)
        default_values, any_checked = burst_config.get_all_simulator_values()
        simulator_input_tree = self.cached_simulator_input_tree
        simulator_input_tree = ABCAdapter.fill_defaults(simulator_input_tree, default_values)
        ### Add simulator tree to session to be available in filters
        self.context.add_adapter_to_session(self.cached_simulator_algo_group, simulator_input_tree, default_values)

        template_specification = {"inputList": simulator_input_tree,
                                  base.KEY_PARAMETERS_CONFIG: True,
                                  'none_checked': not any_checked,
                                  'selectedParametersDictionary': burst_config.simulator_configuration}
        ## Setting this to true means check-boxes are displayed next to all inputs ##
        return self.fill_default_attributes(template_specification)


    @cherrypy.expose
    @using_template("flow/genericAdapterFormFields")
    def get_reduced_simulator_interface(self):
        """
        Get a simulator interface that only contains the inputs that are marked
        as KEY_PARAMETER_CHECKED in the current session.
        """
        burst_config = base.get_from_session(base.KEY_BURST_CONFIG)
        simulator_config = burst_config.simulator_configuration
        ## Fill with stored defaults, and see if any parameter was checked by user ##
        default_values, any_checked = burst_config.get_all_simulator_values()
        simulator_input_tree = self.cached_simulator_input_tree
        simulator_input_tree = ABCAdapter.fill_defaults(simulator_input_tree, default_values)
        ## In case no values were checked just skip tree-cut part and show entire simulator tree ##
        if any_checked:
            simulator_input_tree = self.burst_service.select_simulator_inputs(simulator_input_tree, simulator_config)

        ### Add simulator tree to session to be available in filters
        self.context.add_adapter_to_session(self.cached_simulator_algo_group, simulator_input_tree, default_values)

        template_specification = {"inputList": simulator_input_tree,
                                  base.KEY_PARAMETERS_CONFIG: False,
                                  'draw_hidden_ranges': True}
        return self.fill_default_attributes(template_specification)


    @cherrypy.expose
    @ajax_call()
    def get_previous_selected_rangers(self):
        """
        Retrieve Rangers, if any previously selected in Burst.
        """
        burst_config = base.get_from_session(base.KEY_BURST_CONFIG)
        first_range, second_range = '0', '0'
        if burst_config is not None:
            first_range = burst_config.get_simulation_parameter_value(RANGE_PARAMETER_1) or '0'
            second_range = burst_config.get_simulation_parameter_value(RANGE_PARAMETER_2) or '0'
        return [first_range, second_range]


    @cherrypy.expose
    @ajax_call()
    def save_simulator_configuration(self, exclude_ranges, **data):
        """
        :param exclude_ranges: should be a boolean value. If it is True than the
            ranges will be excluded from the simulation parameters.

        Data is a dictionary with pairs in one of the forms:
            { 'simulator_parameters' : { $name$ : { 'value' : $value$, 'is_disabled' : true/false } },
              'burstName': $burst_name}
        
        The names for the checkboxes next to the parameter with name $name$ is always $name$_checked
        Save this dictionary in an easy to process form from which you could
        rebuild either only the selected entries, or all of the simulator tree
        with the given default values.
        """
        #if the method is called from js then the parameter will be set as string
        exclude_ranges = eval(str(exclude_ranges))
        burst_config = base.get_from_session(base.KEY_BURST_CONFIG)
        if BURST_NAME in data:
            burst_config.name = data[BURST_NAME]
        data = json.loads(data['simulator_parameters'])
        for entry in data:
            if exclude_ranges and (entry.endswith("_checked") or
                                   entry == RANGE_PARAMETER_1 or entry == RANGE_PARAMETER_2):
                continue
            burst_config.update_simulation_parameter(entry, data[entry])
            checkbox_for_entry = entry + "_checked"
            if checkbox_for_entry in data:
                burst_config.update_simulation_parameter(entry, data[checkbox_for_entry], KEY_PARAMETER_CHECKED)


    @cherrypy.expose
    @using_template('base_template')
    @base.settings()
    @logged()
    @context_selected()
    def launch_full_visualizer(self, index_in_tab):
        """
        Launch the full scale visualizer from a small preview from the burst cockpit.
        """
        burst = base.get_from_session(base.KEY_BURST_CONFIG)
        selected_tab = burst.selected_tab
        visualizer = burst.tabs[selected_tab].portlets[int(index_in_tab)].visualizer
        result, input_data, operation_id = self.burst_service.launch_visualization(visualizer, is_preview=False)
        algorithm = self.flow_service.get_algorithm_by_identifier(visualizer.fk_algorithm)

        result[base.KEY_TITLE] = algorithm.name
        result[base.KEY_ADAPTER] = algorithm.algo_group.id
        result[base.KEY_OPERATION_ID] = operation_id
        result[base.KEY_INCLUDE_RESOURCES] = 'flow/included_resources'
        ## Add required field to input dictionary and return it so that it can be used ##
        ## for top right control.                                                    ####
        input_data[base.KEY_ADAPTER] = algorithm.algo_group.id

        if base.KEY_PARENT_DIV not in result:
            result[base.KEY_PARENT_DIV] = ''
        self.context.add_adapter_to_session(algorithm.algo_group, None, copy.deepcopy(input_data))

        self._populate_section(algorithm.algo_group, result)
        result[base.KEY_DISPLAY_MENU] = True
        result[base.KEY_BACK_PAGE] = "/burst"
        result[base.KEY_SUBMIT_LINK] = self.get_url_adapter(algorithm.algo_group.group_category.id,
                                                            algorithm.algo_group.id, 'burst')
        if KEY_CONTROLLS not in result:
            result[KEY_CONTROLLS] = ''
        return self.fill_default_attributes(result)


    def __portlet_config2portlet_entity(self, portlet_cfg):
        """
        From a portlet configuration as it is stored in session, update status and add the index in 
        tab so we can properly display it in the burst page.
        """
        portlet_entity = self.burst_service.get_portlet_by_id(portlet_cfg.portlet_id)
        portlet_status, error_msg = self.burst_service.get_portlet_status(portlet_cfg)
        portlet_entity.error_msg = error_msg
        portlet_entity.status = portlet_status
        portlet_entity.name = portlet_cfg.name
        portlet_entity.index_in_tab = portlet_cfg.index_in_tab
        portlet_entity.td_gid = generate_guid()
        return portlet_entity


    def _validate_burst_name(self, burst_name):
        """
        Validate a new burst name, to have only plain text.
        """
        try:
            form = BurstNameForm()
            form.to_python({'burst_name': burst_name})
        except formencode.Invalid, excep:
            self.logger.error(excep)
            self.logger.exception("Invalid Burst name " + str(burst_name))
            raise excep



class BurstNameForm(formencode.Schema):
    """
    Validate Burst name string
    """
    burst_name = formencode.All(validators.UnicodeString(not_empty=True),
                                validators.Regex(regex=r"^[a-zA-Z\. _\-0-9]*$"))
    
    
    
    