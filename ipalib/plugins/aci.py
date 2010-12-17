# Authors:
#   Rob Crittenden <rcritten@redhat.com>
#   Pavel Zuna <pzuna@redhat.com>
#
# Copyright (C) 2009  Red Hat
# see file 'COPYING' for use and warranty information
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; version 2 only
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
"""
Directory Server Access Control Instructions (ACIs)

ACIs are used to allow or deny access to information. This module is
currently designed to allow, not deny, access.

The aci commands are designed to grant permissions that allow updating
existing entries or adding or deleting new ones. The goal of the ACIs
that ship with IPA is to provide a set of low-level permissions that
grant access to special groups called taskgroups. These low-level
permissions can be combined into roles that grant broader access. These
roles are another type of group, roles.

For example, if you have taskgroups that allow adding and modifying users you
could create a role, useradmin. You would assign users to the useradmin
role to allow them to do the operations defined by the taskgroups.

You can create ACIs that delegate permission so users in group A can write
attributes on group B.

The type option is a map that applies to all entries in the users, groups or
host location. It is primarily designed to be used when granting add
permissions (to write new entries).

An ACI consists of three parts:
1. target
2. permissions
3. bind rules

The target is a set of rules that define which LDAP objects are being
targeted. This can include a list of attributes, an area of that LDAP
tree or an LDAP filter.

The targets include:
- attrs: list of attributes affected
- type: an object type (user, group, host, service, etc)
- memberof: members of a group
- targetgroup: grant access to modify a specific group. This is primarily
  designed to enable users to add or remove members of a specific group.
- filter: A legal LDAP filter used to narrow the scope of the target.
- subtree: Used to apply a rule across an entire set of objects. For example,
  to allow adding users you need to grant "add" permission to the subtree
  ldap://uid=*,cn=users,cn=accounts,dc=example,dc=com. The subtree option
  is a fail-safe for objects that may not be covered by the type option.

The permissions define what the the ACI is allowed to do, and are one or
more of:
1. write - write one or more attributes
2. read - read one or more attributes
3. add - add a new entry to the tree
4. delete - delete an existing entry
5. all - all permissions are granted

Note the distinction between attributes and entries. The permissions are
independent, so being able to add a user does not mean that the user will
be editabe.

The bind rule defines who this ACI grants permissions to. The LDAP server
allows this to be any valid LDAP entry but we encourage the use of
taskgroups so that the rights can be easily shared through roles.

For a more thorough description of access controls see
http://www.redhat.com/docs/manuals/dir-server/ag/8.0/Managing_Access_Control.html

EXAMPLES:

NOTE: ACIs are now added via the permision plugin. These examples are to
demonstrate how the various options work but this is done via the permission
command-line now (see last example).

 Add an ACI so that the group "secretaries" can update the address on any user:
   ipa group-add --desc="Office secretaries" secretaries
   ipa aci-add --attrs=streetAddress --memberof=ipausers --group=secretaries --permissions=write "Secretaries write addresses"

 Show the new ACI:
   ipa aci-show "Secretaries write addresses"

 Add an ACI that allows members of the "addusers" permission to add new users:
   ipa aci-add --type=user --permission=addusers --permissions=add "Add new users"

 Add an ACI that allows members of the editors manage members of the admins group:
   ipa aci-add --permissions=write --attrs=member --targetgroup=admins --group=editors "Editors manage admins"

 Add an ACI that allows members of the admin group to manage the street and zip code of those in the editors group:
   ipa aci-add --permissions=write --memberof=editors --group=admins --attrs=street,postalcode "admins edit the address of editors"

 Add an ACI that allows the admins group manage the street and zipcode of those who work for the boss:
   ipa aci-add --permissions=write --group=admins --attrs=street,postalcode --filter="(manager=uid=boss,cn=users,cn=accounts,dc=example,dc=com)" "Edit the address of those who work for the boss"

 Add an entirely new kind of record to IPA that isn't covered by any of the --type options, creating a permission:
   ipa permission-add  --permissions=add --subtree="cn=*,cn=orange,cn=accounts,dc=example,dc=com" --desc="Add Orange Entries" add_orange


The show command shows the raw 389-ds ACI.

IMPORTANT: When modifying the target attributes of an existing ACI you
must include all existing attributes as well. When doing an aci-mod the
targetattr REPLACES the current attributes, it does not add to them.

"""

from ipalib import api, crud, errors
from ipalib import Object, Command
from ipalib import Flag, Int, List, Str, StrEnum
from ipalib.aci import ACI
from ipalib import output
from ipalib import _, ngettext
if api.env.in_server and api.env.context in ['lite', 'server']:
    from ldap import explode_dn
import logging

_type_map = {
    'user': 'ldap:///uid=*,%s,%s' % (api.env.container_user, api.env.basedn),
    'group': 'ldap:///cn=*,%s,%s' % (api.env.container_group, api.env.basedn),
    'host': 'ldap:///fqdn=*,%s,%s' % (api.env.container_host, api.env.basedn),
    'hostgroup': 'ldap:///cn=*,%s,%s' % (api.env.container_hostgroup, api.env.basedn),
    'service': 'ldap:///krbprincipalname=*,%s,%s' % (api.env.container_service, api.env.basedn),
    'netgroup': 'ldap:///ipauniqueid=*,%s,%s' % (api.env.container_netgroup, api.env.basedn),
    'dns': 'ldap:///idnsname=*,%s,%s' % (api.env.container_dns, api.env.basedn),
}

_valid_permissions_values = [
    u'read', u'write', u'add', u'delete', u'all'
]

class ListOfACI(output.Output):
    type = (list, tuple)
    doc = _('A list of ACI values')

    def validate(self, cmd, entries):
        assert isinstance(entries, self.type)
        for (i, entry) in enumerate(entries):
            if not isinstance(entry, unicode):
                raise TypeError(output.emsg %
                    (cmd.name, self.__class__.__name__,
                    self.name, i, unicode, type(entry), entry)
                )

aci_output = (
    output.Output('result', unicode, 'A string representing the ACI'),
    output.value,
    output.summary,
)



def _make_aci(current, aciname, kw):
    """
    Given a name and a set of keywords construct an ACI.
    """
    # Do some quick and dirty validation.
    t1 = 'type' in kw
    t2 = 'filter' in kw
    t3 = 'subtree' in kw
    t4 = 'targetgroup' in kw
    t5 = 'attrs' in kw
    t6 = 'memberof' in kw
    if t1 + t2 + t3 + t4 > 1:
        raise errors.ValidationError(name='target', error=_('type, filter, subtree and targetgroup are mutually exclusive'))

    if t1 + t2 + t3 + t4 + t5 + t6 == 0:
        raise errors.ValidationError(name='target', error=_('at least one of: type, filter, subtree, targetgroup, attrs or memberof are required'))

    group = 'group' in kw
    permission = 'permission' in kw
    selfaci = 'selfaci' in kw and kw['selfaci'] == True
    if group + permission + selfaci > 1:
        raise errors.ValidationError(name='target', error=_('group, permission and self are mutually exclusive'))
    elif group + permission + selfaci == 0:
        raise errors.ValidationError(name='target', error=_('One of group, permission or self is required'))

    # Grab the dn of the group we're granting access to. This group may be a
    # permission or a user group.
    entry_attrs = []
    if permission:
        # This will raise NotFound if the permission doesn't exist
        try:
            entry_attrs = api.Command['permission_show'](kw['permission'])['result']
        except errors.NotFound, e:
            if 'test' in kw and not kw.get('test'):
                raise e
            else:
                entry_attrs = {'dn': 'cn=%s,%s' % (kw['permission'], api.env.container_permission)}
    elif group:
        # Not so friendly with groups. This will raise
        try:
            entry_attrs = api.Command['group_show'](kw['group'])['result']
        except errors.NotFound:
            raise errors.NotFound(reason=_("Group '%s' does not exist") % kw['group'])

    a = ACI(current)
    a.name = aciname
    a.permissions = kw['permissions']
    if 'selfaci' in kw and kw['selfaci']:
        a.set_bindrule('userdn = "ldap:///self"')
    else:
        dn = entry_attrs['dn']
        a.set_bindrule('groupdn = "ldap:///%s"' % dn)
    if 'attrs' in kw:
        a.set_target_attr(kw['attrs'])
    if 'memberof' in kw:
        entry_attrs = api.Command['group_show'](kw['memberof'])['result']
        a.set_target_filter('memberOf=%s' % entry_attrs['dn'])
    if 'filter' in kw:
        a.set_target_filter(kw['filter'])
    if 'type' in kw:
        target = _type_map[kw['type']]
        a.set_target(target)
    if 'targetgroup' in kw:
        # Purposely no try here so we'll raise a NotFound
        entry_attrs = api.Command['group_show'](kw['targetgroup'])['result']
        target = 'ldap:///%s' % entry_attrs['dn']
        a.set_target(target)
    if 'subtree' in kw:
        # See if the subtree is a full URI
        target = kw['subtree']
        if not target.startswith('ldap:///'):
            target = 'ldap:///%s' % target
        a.set_target(target)

    return a

def _aci_to_kw(ldap, a, test=False):
    """Convert an ACI into its equivalent keywords.

       This is used for the modify operation so we can merge the
       incoming kw and existing ACI and pass the result to
       _make_aci().
    """
    kw = {}
    kw['aciname'] = a.name
    kw['permissions'] = tuple(a.permissions)
    if 'targetattr' in a.target:
        kw['attrs'] = list(a.target['targetattr']['expression'])
        for i in xrange(len(kw['attrs'])):
            kw['attrs'][i] = unicode(kw['attrs'][i])
        kw['attrs'] = tuple(kw['attrs'])
    if 'targetfilter' in a.target:
        target = a.target['targetfilter']['expression']
        if target.startswith('memberOf'):
            kw['memberof'] = unicode(target)
        else:
            kw['filter'] = unicode(target)
    if 'target' in a.target:
        target = a.target['target']['expression']
        found = False
        for k in _type_map.keys():
            if _type_map[k] == target:
                kw['type'] = unicode(k)
                found = True
                break;
        if not found:
            if target.startswith('('):
                kw['filter'] = unicode(target)
            else:
                # See if the target is a group. If so we set the
                # targetgroup attr, otherwise we consider it a subtree
                if api.env.container_group in target:
                    targetdn = unicode(target.replace('ldap:///',''))
                    (dn, entry_attrs) = ldap.get_entry(targetdn, ['cn'])
                    kw['targetgroup'] = entry_attrs['cn'][0]
                else:
                    kw['subtree'] = unicode(target)

    groupdn = a.bindrule['expression']
    groupdn = groupdn.replace('ldap:///','')
    if groupdn == 'self':
        kw['selfaci'] = True
    elif groupdn == 'anyone':
        pass
    else:
        if groupdn.startswith('cn='):
            dn = ''
            entry_attrs = {}
            try:
                (dn, entry_attrs) = ldap.get_entry(groupdn, ['cn'])
            except errors.NotFound, e:
                # FIXME, use real name here
                if test:
                    dn = 'cn=%s,%s' % ('test', api.env.container_permission)
                    entry_attrs = {'cn': [u'test']}
            if api.env.container_permission in dn:
                kw['permission'] = entry_attrs['cn'][0]
            else:
                if 'cn' in entry_attrs:
                    kw['group'] = entry_attrs['cn'][0]

    return kw

def _convert_strings_to_acis(acistrs):
    acis = []
    for a in acistrs:
        try:
            acis.append(ACI(a))
        except SyntaxError, e:
            logging.warn("Failed to parse: %s" % a)
    return acis

def _find_aci_by_name(acis, aciname):
    for a in acis:
        if a.name.lower() == aciname.lower():
            return a
    raise errors.NotFound(reason=_('ACI with name "%s" not found') % aciname)

def validate_permissions(ugettext, permissions):
    valid_permissions = []
    permissions = permissions.split(',')
    for p in permissions:
        p = p.strip().lower()
        if not p in _valid_permissions_values:
             return '"%s" is not a valid permission' % p

def _normalize_permissions(permissions):
    valid_permissions = []
    permissions = permissions.split(',')
    for p in permissions:
        p = p.strip().lower()
        if p not in valid_permissions:
            valid_permissions.append(p)
    return ','.join(valid_permissions)


class aci(Object):
    """
    ACI object.
    """
    INTERNAL = True

    label = _('ACIs')

    takes_params = (
        Str('aciname',
            cli_name='name',
            label=_('ACI name'),
            primary_key=True,
        ),
        Str('permission?',
            cli_name='permission',
            label=_('Permission'),
            doc=_('Permission ACI grants access to'),
        ),
        Str('group?',
            cli_name='group',
            label=_('User group'),
            doc=_('User group ACI grants access to'),
        ),
        List('permissions', validate_permissions,
            cli_name='permissions',
            label=_('Permissions'),
            doc=_('comma-separated list of permissions to grant' \
                '(read, write, add, delete, all)'),
            normalizer=_normalize_permissions,
        ),
        List('attrs?',
            cli_name='attrs',
            label=_('Attributes'),
            doc=_('Comma-separated list of attributes'),
        ),
        StrEnum('type?',
            cli_name='type',
            label=_('Type'),
            doc=_('type of IPA object (user, group, host, hostgroup, service, netgroup)'),
            values=(u'user', u'group', u'host', u'service', u'hostgroup', u'netgroup', u'dns',),
        ),
        Str('memberof?',
            cli_name='memberof',
            label=_('Member of'),  # FIXME: Does this label make sense?
            doc=_('Member of a group'),
        ),
        Str('filter?',
            cli_name='filter',
            label=_('Filter'),
            doc=_('Legal LDAP filter (e.g. ou=Engineering)'),
        ),
        Str('subtree?',
            cli_name='subtree',
            label=_('Subtree'),
            doc=_('Subtree to apply ACI to'),
        ),
        Str('targetgroup?',
            cli_name='targetgroup',
            label=_('Target group'),
            doc=_('Group to apply ACI to'),
        ),
        Flag('selfaci?',
             cli_name='self',
             label=_('Target your own entry (self)'),
             doc=_('Apply ACI to your own entry (self)'),
        ),
    )

api.register(aci)


class aci_add(crud.Create):
    """
    Create new ACI.
    """
    INTERNAL = True
    msg_summary = _('Created ACI "%(value)s"')

    takes_options = (
        Flag('test?',
             doc=_('Test the ACI syntax but don\'t write anything'),
             default=False,
        ),
    )

    def execute(self, aciname, **kw):
        """
        Execute the aci-create operation.

        Returns the entry as it will be created in LDAP.

        :param aciname: The name of the ACI being added.
        :param kw: Keyword arguments for the other LDAP attributes.
        """
        assert 'aciname' not in kw
        ldap = self.api.Backend.ldap2

        newaci = _make_aci(None, aciname, kw)

        (dn, entry_attrs) = ldap.get_entry(self.api.env.basedn, ['aci'])

        acis = _convert_strings_to_acis(entry_attrs.get('aci', []))
        for a in acis:
            # FIXME: add check for permission_group = permission_group
            if a.isequal(newaci) or newaci.name == a.name:
                raise errors.DuplicateEntry()

        newaci_str = unicode(newaci)
        entry_attrs['aci'].append(newaci_str)

        if not kw.get('test', False):
            ldap.update_entry(dn, entry_attrs)

        if kw.get('raw', False):
            result = dict(aci=unicode(newaci_str))
        else:
            result = _aci_to_kw(ldap, newaci, kw.get('test', False))
        return dict(
            result=result,
            value=aciname,
        )

api.register(aci_add)


class aci_del(crud.Delete):
    """
    Delete ACI.
    """
    INTERNAL = True
    has_output = output.standard_delete
    msg_summary = _('Deleted ACI "%(value)s"')

    def execute(self, aciname, **kw):
        """
        Execute the aci-delete operation.

        :param aciname: The name of the ACI being added.
        :param kw: unused
        """
        assert 'aciname' not in kw
        ldap = self.api.Backend.ldap2

        (dn, entry_attrs) = ldap.get_entry(self.api.env.basedn, ['aci'])

        acistrs = entry_attrs.get('aci', [])
        acis = _convert_strings_to_acis(acistrs)
        aci = _find_aci_by_name(acis, aciname)
        for a in acistrs:
            candidate = ACI(a)
            if aci.isequal(candidate):
                acistrs.remove(a)
                break

        entry_attrs['aci'] = acistrs

        ldap.update_entry(dn, entry_attrs)

        return dict(
            result=True,
            value=aciname,
        )

api.register(aci_del)


class aci_mod(crud.Update):
    """
    Modify ACI.
    """
    INTERNAL = True
    has_output_params = (
        Str('aci',
            label=_('ACI'),
        ),
    )

    msg_summary = _('Modified ACI "%(value)s"')

    def execute(self, aciname, **kw):
        ldap = self.api.Backend.ldap2

        (dn, entry_attrs) = ldap.get_entry(self.api.env.basedn, ['aci'])

        acis = _convert_strings_to_acis(entry_attrs.get('aci', []))
        aci = _find_aci_by_name(acis, aciname)

        # The strategy here is to convert the ACI we're updating back into
        # a series of keywords. Then we replace any keywords that have been
        # updated and convert that back into an ACI and write it out.
        newkw =  _aci_to_kw(ldap, aci)
        if 'selfaci' in newkw and newkw['selfaci'] == True:
            # selfaci is set in aci_to_kw to True only if the target is self
            kw['selfaci'] = True
        for k in kw.keys():
            newkw[k] = kw[k]
        if 'aciname' in newkw:
            del newkw['aciname']

        # _make_aci is what is run in aci_add and validates the input.
        # Do this before we delete the existing ACI.
        newaci = _make_aci(None, aciname, newkw)
        if aci.isequal(newaci):
            raise errors.EmptyModlist()

        self.api.Command['aci_del'](aciname)

        result = self.api.Command['aci_add'](aciname, **newkw)['result']

        if kw.get('raw', False):
            result = dict(aci=unicode(newaci))
        else:
            result = _aci_to_kw(ldap, newaci)
        return dict(
            result=result,
            value=aciname,
        )

api.register(aci_mod)


class aci_find(crud.Search):
    """
    Search for ACIs.

    Returns a list of ACIs

    EXAMPLES:

     To find all ACIs that apply directly to members of the group ipausers:
       ipa aci-find --memberof=ipausers

     To find all ACIs that grant add access:
       ipa aci-find --permissions=add

    Note that the find command only looks for the given text in the set of
    ACIs, it does not evaluate the ACIs to see if something would apply.
    For example, searching on memberof=ipausers will find all ACIs that
    have ipausers as a memberof. There may be other ACIs that apply to
    members of that group indirectly.
    """
    INTERNAL = True
    msg_summary = ngettext('%(count)d ACI matched', '%(count)d ACIs matched', 0)

    def execute(self, term, **kw):
        ldap = self.api.Backend.ldap2

        (dn, entry_attrs) = ldap.get_entry(self.api.env.basedn, ['aci'])

        acis = _convert_strings_to_acis(entry_attrs.get('aci', []))
        results = []

        if term:
            term = term.lower()
            for a in acis:
                if a.name.lower().find(term) != -1 and a not in results:
                    results.append(a)
            acis = list(results)
        else:
            results = list(acis)

        if 'aciname' in kw:
            for a in acis:
                if a.name != kw['aciname']:
                    results.remove(a)
            acis = list(results)

        if 'attrs' in kw:
            for a in acis:
                if not 'targetattr' in a.target:
                    results.remove(a)
                    continue
                alist1 = sorted(
                    [t.lower() for t in a.target['targetattr']['expression']]
                )
                alist2 = sorted([t.lower() for t in kw['attrs']])
                if len(set(alist1) & set(alist2)) != len(alist2):
                    results.remove(a)
            acis = list(results)

        if 'permission' in kw:
            try:
                self.api.Command['permission_show'](
                    kw['permission']
                )
            except errors.NotFound:
                pass
            else:
                for a in acis:
                    if a.bindrule['expression'] != ('ldap:///%s' % dn):
                        results.remove(a)
                acis = list(results)

        if 'permissions' in kw:
            for a in acis:
                alist1 = sorted(a.permissions)
                alist2 = sorted(kw['permissions'])
                if len(set(alist1) & set(alist2)) != len(alist2):
                    results.remove(a)
            acis = list(results)

        if 'memberof' in kw:
            try:
                result = self.api.Command['group_show'](
                    kw['memberof']
                )['result']
                dn = result['dn']
            except errors.NotFound:
                pass
            else:
                memberof_filter = '(memberOf=%s)' % dn
                for a in acis:
                    if 'targetfilter' in a.target:
                        targetfilter = a.target['targetfilter']['expression']
                        if targetfilter != memberof_filter:
                            results.remove(a)
                    else:
                        results.remove(a)

        if 'type' in kw:
            for a in acis:
                if 'target' in a.target:
                    target = a.target['target']['expression']
                else:
                    results.remove(a)
                    continue
                found = False
                for k in _type_map.keys():
                    if _type_map[k] == target and kw['type'] == k:
                        found = True
                        break;
                if not found:
                    try:
                        results.remove(a)
                    except ValueError:
                        pass

        if 'selfaci' in kw and kw['selfaci'] == True:
            for a in acis:
                if a.bindrule['expression'] != u'ldap:///self':
                    try:
                        results.remove(a)
                    except ValueError:
                        pass

        if 'group' in kw:
            for a in acis:
                groupdn = a.bindrule['expression']
                groupdn = groupdn.replace('ldap:///','')
                cn = None
                if groupdn.startswith('cn='):
                    cn = explode_dn(groupdn)[0]
                    cn = cn.replace('cn=','')
                if cn is None or cn != kw['group']:
                    try:
                        results.remove(a)
                    except ValueError:
                        pass

        if 'targetgroup' in kw:
            for a in acis:
                found = False
                if 'target' in a.target:
                    target = a.target['target']['expression']
                    if api.env.container_group in target:
                        targetdn = unicode(target.replace('ldap:///',''))
                        cn = explode_dn(targetdn)[0]
                        cn = cn.replace('cn=','')
                        if cn == kw['targetgroup']:
                            found = True
                if not found:
                    try:
                        results.remove(a)
                    except ValueError:
                        pass

        # TODO: searching by: filter, subtree

        acis = []
        for result in results:
            if kw.get('raw', False):
                aci = dict(aci=unicode(result))
            else:
                aci = _aci_to_kw(ldap, result)
            acis.append(aci)

        return dict(
            result=acis,
            count=len(acis),
            truncated=False,
        )

api.register(aci_find)


class aci_show(crud.Retrieve):
    """
    Display a single ACI given an ACI name.
    """
    INTERNAL = True

    has_output_params = (
        Str('aci',
            label=_('ACI'),
        ),
    )

    def execute(self, aciname, **kw):
        """
        Execute the aci-show operation.

        Returns the entry

        :param uid: The login name of the user to retrieve.
        :param kw: unused
        """
        ldap = self.api.Backend.ldap2

        (dn, entry_attrs) = ldap.get_entry(self.api.env.basedn, ['aci'])

        acis = _convert_strings_to_acis(entry_attrs.get('aci', []))

        aci = _find_aci_by_name(acis, aciname)
        if kw.get('raw', False):
            result = dict(aci=unicode(aci))
        else:
            result = _aci_to_kw(ldap, aci)
        return dict(
            result=result,
            value=aciname,
        )

api.register(aci_show)


class aci_rename(crud.Update):
    """
    Rename an ACI.
    """
    INTERNAL = True
    has_output_params = (
        Str('aci',
            label=_('ACI'),
        ),
    )

    takes_options = (
        Str('newname',
             doc=_('New ACI name'),
        ),
    )

    msg_summary = _('Renameed ACI to "%(value)s"')

    def execute(self, aciname, **kw):
        ldap = self.api.Backend.ldap2

        (dn, entry_attrs) = ldap.get_entry(self.api.env.basedn, ['aci'])

        acis = _convert_strings_to_acis(entry_attrs.get('aci', []))
        aci = _find_aci_by_name(acis, aciname)

        for a in acis:
            if kw['newname'] == a.name:
                raise errors.DuplicateEntry()

        # The strategy here is to convert the ACI we're updating back into
        # a series of keywords. Then we replace any keywords that have been
        # updated and convert that back into an ACI and write it out.
        newkw =  _aci_to_kw(ldap, aci)
        if 'selfaci' in newkw and newkw['selfaci'] == True:
            # selfaci is set in aci_to_kw to True only if the target is self
            kw['selfaci'] = True
        if 'aciname' in newkw:
            del newkw['aciname']

        # _make_aci is what is run in aci_add and validates the input.
        # Do this before we delete the existing ACI.
        newaci = _make_aci(None, kw['newname'], newkw)

        self.api.Command['aci_del'](aciname)

        result = self.api.Command['aci_add'](kw['newname'], **newkw)['result']

        if kw.get('raw', False):
            result = dict(aci=unicode(newaci))
        else:
            result = _aci_to_kw(ldap, newaci)
        return dict(
            result=result,
            value=kw['newname'],
        )

api.register(aci_rename)
