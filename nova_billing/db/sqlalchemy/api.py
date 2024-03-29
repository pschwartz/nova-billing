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
Nova Billing API.
"""

from datetime import datetime

from sqlalchemy.sql import func, and_, or_
from sqlalchemy.sql.expression import select

from nova import flags
from nova import utils

from nova_billing.db.sqlalchemy import models
from nova_billing.db.sqlalchemy.models import InstanceSegment, InstanceInfo
from nova_billing.db.sqlalchemy.session import get_session, get_engine
from nova_billing import utils


FLAGS = flags.FLAGS

def configure_backend():
    """
    Perform backend initialization.
    """
    models.register_models()


def instance_info_create(values, session=None):
    """
    Create and store an ``InstanceInfo`` object in the database.
    """
    entity_ref = InstanceInfo()
    entity_ref.update(values)
    entity_ref.save(session=session)
    return entity_ref


def instance_info_get(self, id, session=None):
    """
    Get an ``InstanceInfo`` object with the given ``id``.
    """
    if not session:
        session = get_session()
    result = session.query(InstanceInfo).filter_by(id=id).first()
    return result


def instance_segment_create(values, session=None):
    """
    Create and store an ``InstanceSegment`` object in the database.
    """
    entity_ref = InstanceSegment()
    entity_ref.update(values)
    entity_ref.save(session=session)
    return entity_ref


def instance_info_get_latest(instance_id, session=None):
    """
    Get the latest ``InstanceInfo`` object with the given ``instance_id``.
    """
    if not session:
        session = get_session()
    result = session.query(func.max(InstanceInfo.id)).\
        filter_by(instance_id=instance_id).first()
    return result[0]


def instance_segment_end(instance_id, end_at, session=None):
    """
    End all ``InstanceSegment`` objects with  the given ``instance_id``.
    """
    if not session:
        session = get_session()
    session.execute(InstanceSegment.__table__.update().
        values(end_at=end_at).where(InstanceSegment.
        instance_info_id.in_(select([InstanceInfo.id]).
        where(InstanceInfo.instance_id==instance_id))))


def instances_on_interval(period_start, period_stop, project_id=None):
    """
    Retrieve statistics for the given interval [``period_start``, ``period_stop``]. 
    ``project_id=None`` means all projects.

    Example of the returned value:

    .. code-block:: python

        {
            "systenant": {
                12: {
                    "created_at": datetime.datetime(2011, 1, 1),
                    "destroyed_at": datetime.datetime(2011, 1, 2),
                    "usage": {"local_gb": 56, "memory_mb": 89, "vcpus": 4},
                },
                14: {
                    "created_at": datetime.datetime(2011, 1, 4),
                    "destroyed_at": datetime.datetime(2011, 2, 1),
                    "usage": {"local_gb": 18, "memory_mb": 45, "vcpus": 5},
                },
            },
            "tenant12": {
                24: {
                    "created_at": datetime.datetime(2011, 1, 1),
                    "destroyed_at": datetime.datetime(2011, 1, 2),
                    "usage": {"local_gb": 33, "memory_mb": 12, "vcpus": 8},
                },
            }
        }

    :returns: a dictionary where keys are project ids and values are project statistics.
    """
    session = get_session()
    result = session.query(InstanceSegment, InstanceInfo).\
                join(InstanceInfo).\
                filter(InstanceSegment.begin_at < period_stop).\
                filter(or_(InstanceSegment.end_at > period_start,
                           InstanceSegment.end_at == None))
    if project_id:
        result = result.filter(InstanceInfo.project_id == project_id)

    retval = {}
    inst_by_id = {}
    for segment, info in result:
        if not retval.has_key(info.project_id):
            retval[info.project_id] = {}
        try:
            inst_descr = inst_by_id[info.instance_id]
        except KeyError:
            inst_descr = {
                "created_at": None,
                "destroyed_at": None,
                "lifetime": 0,
                "usage": {}
            }
            retval[info.project_id][info.instance_id] = inst_descr
            inst_by_id[info.instance_id] = inst_descr
        begin_at = max(segment.begin_at, period_start)
        end_at = min(segment.end_at or datetime.utcnow(), period_stop)
        utils.usage_add(inst_descr["usage"], begin_at, end_at,
                  segment.segment_type, info)

    result = session.query(InstanceSegment,
        func.min(InstanceSegment.begin_at).label("min_start"),
        func.max(InstanceSegment.begin_at).label("max_start"),
        func.max(InstanceSegment.end_at).label("max_stop"),
        InstanceInfo.instance_id).\
        join(InstanceInfo).\
        group_by(InstanceInfo.instance_id).\
        filter(InstanceSegment.begin_at < period_stop).\
        filter(or_(InstanceSegment.end_at > period_start,
                   InstanceSegment.end_at == None))
    if project_id:
        result = result.filter(InstanceInfo.project_id == project_id)

    for row in result:
        inst_descr = inst_by_id.get(row.instance_id, None)
        if not inst_descr:
            continue
        inst_descr["created_at"] = row.min_start
        if row.max_stop is None or row.max_start < row.max_stop:
            inst_descr["destroyed_at"] = row.max_stop

    return retval
