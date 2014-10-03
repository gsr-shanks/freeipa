/*
 *  Authors:
 *    Petr Vobornik <pvoborni@redhat.com>
 *
 * Copyright (C) 2014 Red Hat
 * see file 'COPYING' for use and warranty information
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

define([
        './ipa',
        './jquery',
        './menu',
        './phases',
        './reg',
        './rpc',
        './text',
        './details',
        './facet',
        './search',
        './entity'],
            function(IPA, $, menu, phases, reg, rpc, text, mod_details, mod_facet) {
/**
 * ID Views module
 * @class
 * @singleton
 */
var idviews = IPA.idviews = {};

var make_spec = function() {
return {
    name: 'idview',
    enable_test: function() {
        return true;
    },
    facet_groups: [
        {
            name: 'appliedto',
            label: '@i18n:objects.idview.appliesto_tab'
        },
        {
            name: 'overrides',
            label: '@i18n:objects.idview.overrides_tab'
        },
        'settings'
    ],
    facets: [
        {
            $type: 'search',
            columns: [
                'cn',
                'description'
            ],
            actions: [
                'idview_unapply_host',
                'idview_unapply_hostgroups'
            ],
            control_buttons: [
                {
                    name: 'idview_unapply_host',
                    label: '@i18n:objects.idview.unapply_hosts_all',
                    icon: 'fa-trash-o'
                },
                {
                    name: 'idview_unapply_hostgroups',
                    label: '@i18n:objects.idview.unapply_hostgroups',
                    icon: 'fa-trash-o'
                }
            ]
        },
        {
            $type: 'details',
            actions: [
                'delete'
            ],
            header_actions: ['delete'],
            state: {
            },
            sections: [
                {
                    name: 'details',
                    fields: [
                        'cn',
                        {
                            $type: 'textarea',
                            name: 'description'
                        }
                    ]
                }
            ]
        },
        {
            $type: 'nested_search',
            facet_group: 'overrides',
            nested_entity: 'idoverrideuser',
            search_all_entries: true,
            label: '@mo:idoverrideuser.label',
            tab_label: '@mo:idoverrideuser.label',
            name: 'idoverrideuser',
            columns: [
                {
                    name: 'ipaanchoruuid',
                    label: '@i18n:objects.idoverrideuser.anchor_label'
                },
                'uid',
                'uidnumber',
                'homedirectory',
                'description'
            ]
        },
        {
            $type: 'nested_search',
            facet_group: 'overrides',
            nested_entity: 'idoverridegroup',
            search_all_entries: true,
            label: '@mo:idoverridegroup.label',
            tab_label: '@mo:idoverridegroup.label',
            name: 'idoverridegroup',
            columns: [
                {
                    name: 'ipaanchoruuid',
                    label: '@i18n:objects.idoverridegroup.anchor_label'
                },
                'cn',
                'gidnumber',
                'description'
            ]
        },
        {
            $type: 'idview_appliedtohosts',
            name: 'appliedtohosts',
            attribute: 'appliedtohosts',
            tab_label: '@i18n:objects.idview.appliedtohosts',
            facet_group: 'appliedto',
            actions: [
                'idview_apply',
                'idview_apply_hostgroups',
                'idview_unapply',
                'idview_unapply_hostgroups'
            ],
            control_buttons: [
                {
                    name: 'idview_unapply',
                    label: '@i18n:objects.idview.unapply_hosts',
                    icon: 'fa-trash-o'
                },
                {
                    name: 'idview_unapply_hostgroups',
                    label: '@i18n:objects.idview.unapply_hostgroups',
                    icon: 'fa-trash-o'
                },
                {
                    name: 'idview_apply',
                    label: '@i18n:objects.idview.apply_hosts',
                    icon: 'fa-plus'
                },
                {
                    name: 'idview_apply_hostgroups',
                    label: '@i18n:objects.idview.apply_hostgroups',
                    icon: 'fa-plus'
                }
            ],
            columns: [
                {
                    name: 'appliedtohosts',
                    label: '@mo:host.label_singular',
                    link: true,
                    target_entity: 'host',
                    target_facet: 'details'
                }
            ]
        }
    ],

    adder_dialog: {
        fields: [
            'cn',
            {
                $type: 'textarea',
                name: 'description'
            }
        ]
    }
};};

var make_idoverrideuser_spec = function() {
return {
    name: 'idoverrideuser',
    enable_test: function() {
        return true;
    },
    policies:[
        {
            $factory: IPA.facet_update_policy,
            source_facet: 'details',
            dest_entity: 'idview',
            dest_facet: 'idoverrideuser'
        }
    ],
    containing_entity: 'idview',
    facets: [
        {
            $type: 'details',
            disable_breadcrumb: false,
            containing_facet: 'idoverrideuser',
            actions: [
                'delete'
            ],
            header_actions: ['delete'],
            state: {
            },
            sections: [
                {
                    name: 'details',
                    fields: [
                        {
                            $type: 'link',
                            name: 'ipaanchoruuid',
                            label: '@i18n:objects.idoverrideuser.anchor_label',
                            other_entity: 'user'
                        },
                        {
                            $type: 'textarea',
                            name: 'description'
                        },
                        'uid',
                        'gecos',
                        'uidnumber',
                        'gidnumber',
                        'loginshell',
                        'homedirectory',
                        {
                            $type: 'sshkeys',
                            name: 'ipasshpubkey',
                            label: '@i18n:objects.sshkeystore.keys'
                        }
                    ]
                }
            ]
        }
    ],

    adder_dialog: {
        fields: [
            {
                $type: 'entity_select',
                label: '@i18n:objects.idoverrideuser.anchor_label',
                name: 'ipaanchoruuid',
                other_entity: 'user',
                other_field: 'uid',
                editable: true,
                tooltip: '@i18n:objects.idoverrideuser.anchor_tooltip'
            },
            'uid',
            'gecos',
            'uidnumber',
            'gidnumber',
            'loginshell',
            'homedirectory',
            {
                $type: 'textarea',
                name: 'description'
            }
        ]
    }
};};

var make_idoverridegroup_spec = function() {
return {
    name: 'idoverridegroup',
    enable_test: function() {
        return true;
    },
    policies:[
        {
            $factory: IPA.facet_update_policy,
            source_facet: 'details',
            dest_entity: 'idview',
            dest_facet: 'idoverridegroup'
        }
    ],
    containing_entity: 'idview',
    facets: [
        {
            $type: 'details',
            disable_breadcrumb: false,
            containing_facet: 'idoverridegroup',
            actions: [
                'delete'
            ],
            header_actions: ['delete'],
            state: {
            },
            sections: [
                {
                    name: 'details',
                    fields: [
                        {
                            $type: 'link',
                            name: 'ipaanchoruuid',
                            label: '@i18n:objects.idoverridegroup.anchor_label',
                            other_entity: 'group'
                        },
                        {
                            $type: 'textarea',
                            name: 'description'
                        },
                        'cn',
                        'gidnumber'
                    ]
                }
            ]
        }
    ],

    adder_dialog: {
        fields: [
             {
                $type: 'entity_select',
                label: '@i18n:objects.idoverridegroup.anchor_label',
                name: 'ipaanchoruuid',
                other_entity: 'group',
                other_field: 'cn',
                editable: true,
                tooltip: '@i18n:objects.idoverridegroup.anchor_tooltip'
            },
            'cn',
            'gidnumber',
            {
                $type: 'textarea',
                name: 'description'
            }
        ]
    }
};};


/**
 * Facet for hosts which have current id view applied on
 *
 * @class idviews.appliedtohosts_facet
 * @extends IPA.attribute_facet
 */
idviews.appliedtohosts_facet = function(spec, no_init) {

    spec = spec || {};

    var that = IPA.attribute_facet(spec, no_init);

    /**
     * @inheritDoc
     */
    that.get_refresh_command = function() {
        var command = that.attribute_get_refresh_command();
        command.set_option('show_hosts', true);
        return command;
    };

    return that;
};

/**
 * Apply Id view on hosts on hostgroup action base class
 *
 * @class idviews.apply_action
 * @extends IPA.action
 */
idviews.apply_action = function(spec) {

    spec = spec || {};
    spec.name = spec.name || 'idview_apply';
    spec.label = spec.label || '@i18n:objects.idview.apply_hosts';

    var that = IPA.action(spec);

    /**
     * Confirm button label
     * @property {string}
     */
    that.confirm_button_label = spec.confirm_button_label || '@i18n:buttons.apply';

    /**
     * Entity to apply
     * @property {entity.entity|string}
     */
    that.other_entity = spec.other_entity || 'host';

    /**
     * Dialog title
     * @property {string}
     */
    that.dialog_title = spec.dialog_title || '@i18n:objects.idview.apply_hosts_title';

    /**
     * Method
     * @property {string}
     */
    that.method = spec.method || 'apply';

    /**
     * Success message
     * @property {string}
     */
    that.success_msg = spec.success_msg || '@i18n:association.added';

    /**
     * @inheritDoc
     */
    that.execute_action = function(facet, on_success, on_error) {

        that.show_dialog(facet);
    };

    /**
     * Create and open dialog
     */
    that.show_dialog = function(facet) {

        var pkey = facet.get_pkey();
        var other_entity = reg.entity.get(that.other_entity);
        var other_entity_label = other_entity.metadata.label;
        var exclude = that.get_exclude(facet);
        var title = text.get(that.dialog_title);
        title = title.replace('${entity}', other_entity_label);
        title = title.replace('${primary_key}', pkey);

        var dialog = IPA.association_adder_dialog({
            title: title,
            entity: facet.entity,
            pkey: pkey,
            other_entity: other_entity,
            attribute_member: that.attribute_member,
            exclude: exclude,
            add_button_label: that.confirm_button_label
        });

        dialog.execute = function() {
            var values = dialog.get_selected_values();
            var command = that.get_command(
                facet,
                values,
                function(data) {
                    that.notify_change(facet);
                    dialog.close();
                    var succeeded = IPA.get_succeeded(data);
                    var msg = text.get(that.success_msg).replace('${count}', succeeded);
                    IPA.notify_success(msg);
                },
                function() {
                    that.notify_change(facet);
                    dialog.close();
                });
            command.execute();
            return command;
        };

        dialog.open();
    };

    /**
     * Construct action command
     */
    that.get_command = function(facet, values, on_success, on_error) {
        var other_entity = reg.entity.get(that.other_entity);
        var pkey = facet.get_pkey();
        var args = pkey ? [pkey] : [];
        var command = rpc.command({
                entity: 'idview',
                method: that.method,
                args: args,
                options: {},
                on_success: on_success,
                on_error: on_error
            });

        command.set_option(other_entity.name, values);
        return command;
    };

    /**
     * Get pkeys which should be excluded from offered pkeys in the dialog
     *
     * By default it works only for 'host' of 'appliedtohosts' facet since
     * other facets might contain completely different values or might have
     * different API.
     *
     * @param {facet.facet} facet
     * @return {string[]}
     */
    that.get_exclude = function(facet) {
        if (facet && facet.name === 'appliedtohosts' &&
                that.other_entity === 'host') {
            var records = facet.get_records_map(facet.data);
            return records.keys;
        }
        return [];
    };

    /**
     * Notify idview.appliedtohosts facet that there were possible changes
     * and a refresh is needed.
     */
    that.notify_change = function(current_facet) {

        if (current_facet && current_facet.name === 'appliedtohosts') {
            current_facet.refresh();
        } else {
            reg.entity.get('idview').
                get_facet('appliedtohosts').
                set_expired_flag();
        }
    };

    that.apply_action_get_command = that.get_command;

    return that;
};


/**
 * Apply Id view on hosts of a hostgroup
 *
 * @class idviews.apply_hostgroup_action
 * @extends idviews.apply_action
 */
idviews.apply_hostgroups_action = function(spec) {

    spec = spec || {};
    spec.name = spec.name || 'idview_apply_hostgroups';
    spec.label = spec.label || '@i18n:objects.idview.apply_hostgroups';
    spec.other_entity = spec.other_entity || 'hostgroup';
    spec.dialog_title = spec.dialog_title || '@i18n:objects.idview.apply_hostgroups_title';

    var that = idviews.apply_action(spec);
    return that;
};

/**
 * Unapply Id view from hosts
 *
 * @class idviews.unapply_host_action
 * @extends idviews.apply_action
 */
idviews.unapply_host_action = function(spec) {

    spec = spec || {};
    spec.name = spec.name || 'idview_unapply_host';
    spec.label = spec.label || '@i18n:objects.idview.unapply_hosts_all';
    spec.other_entity = spec.other_entity || 'host';
    spec.method = spec.method || 'unapply';
    spec.dialog_title = spec.dialog_title || '@i18n:objects.idview.unapply_hosts_all_title';
    spec.confirm_button_label = spec.confirm_button_label || '@i18n:buttons.unapply';
    spec.success_msg = spec.success_msg || '@i18n:association.removed';

    var that = idviews.apply_action(spec);

    /**
     * @inheritDoc
     */
    that.get_command = function(facet, values, on_success, on_error) {
        var command = that.apply_action_get_command(facet, values, on_success, on_error);
        // idview_unapply doesn't support primary keys to narrow down idviews
        // to un-apply yet
        command.args = [];
        return command;
    };

    return that;
};

/**
 * Unapply Id view from all hosts of a hostgroup
 *
 * @class idviews.unapply_hostgroups_action
 * @extends idviews.unapply_host_action
 */
idviews.unapply_hostgroups_action = function(spec) {

    spec = spec || {};
    spec.name = spec.name || 'idview_unapply_hostgroups';
    spec.label = spec.label || '@i18n:objects.idview.unapply_hostgroups';
    spec.other_entity = spec.other_entity || 'hostgroup';
    spec.dialog_title = spec.dialog_title || '@i18n:objects.idview.unapply_hostgroups_all_title';

    var that = idviews.unapply_host_action(spec);
    return that;
};

/**
 * Unapply Id view from selected hosts
 *
 * @class idviews.unapply_action
 * @extends idviews.unapply_host_action
 */
idviews.unapply_action = function(spec) {

    spec = spec || {};
    spec.name = spec.name || 'idview_unapply';
    spec.label = spec.label || '@i18n:objects.idview.unapply_hosts';
    spec.enable_cond = spec.enable_cond || ['item-selected'];
    spec.enabled = spec.enabled === undefined ? false : spec.enabled;
    spec.confirm_button_label = spec.confirm_button_label || '@i18n:buttons.unapply';
    spec.method = spec.method || 'unapply';
    spec.dialog_title = spec.dialog_title || '@i18n:objects.idview.unapply_hosts_title';

    var that = idviews.unapply_host_action(spec);

    /**
     * @inheritDoc
     */
    that.show_dialog = function(facet, current_pkeys) {

        var selected_values = facet.get_selected_values();

        if (!selected_values.length) {
            var message = text.get('@i18n:dialogs.remove_empty');
            IPA.notify(message, 'error');
            return;
        }

        var pkey = facet.get_pkey();
        var other_entity = reg.entity.get('host');
        var title = text.get(that.dialog_title);
        title = title.replace('${primary_key}', pkey);

        var dialog = IPA.association_deleter_dialog({
            title: title,
            entity: facet.entity,
            pkey: pkey,
            other_entity: other_entity,
            values: selected_values,
            method: that.method,
            ok_label: that.confirm_button_label,
            message: '@i18n:objects.idview.unapply_hosts_confirm'
        });

        dialog.execute = function() {
            var command = that.get_command(
                facet,
                selected_values,
                function(data) {
                    that.notify_change(facet);
                    var succeeded = IPA.get_succeeded(data);
                    var msg = text.get('@i18n:association.removed').replace('${count}', succeeded);
                    IPA.notify_success(msg);
                },
                function() {
                    that.notify_change(facet);
                }
            );
            command.execute();
        };

        dialog.open();
    };

    return that;
};

/**
 * ID View entity specification object
 * @member idviews
 */
idviews.spec = make_spec();

/**
 * ID user override entity specification object
 * @member idviews
 */
idviews.idoverrideuser_spec = make_idoverrideuser_spec();

/**
 * ID group override entity specification object
 * @member idviews
 */
idviews.idoverridegroup_spec = make_idoverridegroup_spec();

/**
 * Register entity
 * @member idviews
 */
idviews.register = function() {
    var e = reg.entity;
    var f = reg.facet;
    var a = reg.action;
    e.register({type: 'idview', spec: idviews.spec});
    e.register({type: 'idoverrideuser', spec: idviews.idoverrideuser_spec});
    e.register({type: 'idoverridegroup', spec: idviews.idoverridegroup_spec});
    f.copy('attribute', 'idview_appliedtohosts', {
        factory: idviews.appliedtohosts_facet
    });
    a.register('idview_apply', idviews.apply_action);
    a.register('idview_apply_hostgroups', idviews.apply_hostgroups_action);
    a.register('idview_unapply', idviews.unapply_action);
    a.register('idview_unapply_host', idviews.unapply_host_action);
    a.register('idview_unapply_hostgroups', idviews.unapply_hostgroups_action);
};

phases.on('registration', idviews.register);

return idviews;
});