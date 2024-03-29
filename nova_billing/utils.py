# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Nova Billing
#    Copyright (C) GridDynamics Openstack Core Team, GridDynamics
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
Miscellaneous utility functions:

- usage calculations for different VM states;
- datetime manipulations;
- other.
"""

from datetime import datetime
from nova_billing import vm_states


def total_seconds(td):
    """This function is added for portability
    because timedelta.total_seconds() 
    was introduced only in python 2.7."""
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6


def now():
    """
    Return current time in UTC.
    """
    return datetime.utcnow()


def str_to_datetime(dtstr):
    """
    Convert string to datetime.datetime. String should be in ISO 8601 format.
    The function returns ``None`` for invalid date string.
    """
    if not dtstr:
        return None
    if dtstr.endswith("Z"):
        dtstr = dtstr[:-1]
    for fmt in ("%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(dtstr, fmt)
        except ValueError:
            pass
    return None


def datetime_to_str(dt):
    """
    Convert datetime.datetime instance to string.
    Used for JSONization.
    """
    return ("%sZ" % dt.isoformat()) if dt else None


used_resources = {
    vm_states.ACTIVE: ("local_gb", "memory_mb", "vcpus"),
    vm_states.SUSPENDED: ("local_gb", "memory_mb"),
    vm_states.PAUSED: ("local_gb", "memory_mb"),
    vm_states.STOPPED: ("local_gb", ),
}


def usage_add(usage, begin_at, end_at, vm_state, instance_info):
    """
    Increment used resource statistics depending on ``vm_state``.
    Statistics is measured in (resource unit * second).
    """
    length = total_seconds(end_at - begin_at)
    for key in ("local_gb", "memory_mb", "vcpus"):
        usage[key] = (usage.get(key, 0) +
            (length * instance_info[key]
             if key in used_resources.get(vm_state, [])
             else 0))


def usage_to_hours(usage):
    """
    Convert usage measured for seconds to hours.
    """
    return dict([(key + "_h", usage[key] / 3600.0) for key in usage])


def dict_add(a, b):
    """
    Increment all keys in ``a`` on keys in ``b``.
    """
    for key in b:
        a[key] = a.get(key, 0) + b[key]
