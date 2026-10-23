"""Undo snapshots must restore sketches whose data is linked or overridden.

Interactive tools roll back to a snapshot on every preview update and on
cancel, which cleared and rebuilt the constraint collections of every sketch.
Items can't be removed from a collection of library-override data, so having
such a sketch in the scene raised ``TypeError: bpy_prop_collection.remove() not
supported for this collection`` from any tool.
"""

import os
import tempfile

import bpy

from ..operators.base_2d import Operator2d
from ..operators.base_stateful import GenericEntityOp
from .utils import Sketch2dTestCase


class TestRestoreConstraintsOverride(Sketch2dTestCase):
    def _horizontal_line(self):
        a = self.add_point((0, 0))
        b = self.add_point((1, 0.2))
        line = self.add_line(a, b)
        self.sketch.constraints.add_horizontal(curve_id_1=line.curve_id)
        return line

    def _override_sketch_data(self):
        obj = self.sketch.target_object
        local = obj.data
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "lib.blend")
            bpy.data.libraries.write(path, {local})
            with bpy.data.libraries.load(path, link=True) as (_src, dst):
                dst.hair_curves = [local.name]
            linked = dst.hair_curves[0]
            override = linked.override_create(remap_local_usages=False)
        obj.data = override

        def cleanup():
            obj.data = local
            bpy.data.batch_remove([override, linked, linked.library])

        self.addCleanup(cleanup)
        return override

    def _count(self, data):
        return sum(len(c) for c in data.sketch_constraints.get_lists())

    def _roundtrip(self, op_cls):
        self._horizontal_line()
        data = self._override_sketch_data()
        self.assertIsNotNone(data.override_library)
        count = self._count(data)
        self.assertEqual(count, 1)

        op = op_cls.__new__(op_cls)
        op.restore_snapshot(self.context, op.create_snapshot(self.context))

        self.assertEqual(self._count(data), count)

    def test_full_snapshot_restore_with_override_sketch(self):
        self._roundtrip(GenericEntityOp)

    def test_draw_snapshot_restore_with_override_sketch(self):
        self._roundtrip(Operator2d)

    def test_local_sketch_still_restores_constraints(self):
        line = self._horizontal_line()
        data = self.sketch.target_object.data
        op = GenericEntityOp.__new__(GenericEntityOp)
        snapshot = op.create_snapshot(self.context)
        self.sketch.constraints.add_vertical(curve_id_1=line.curve_id)
        self.assertEqual(self._count(data), 2)

        op.restore_snapshot(self.context, snapshot)

        self.assertEqual(self._count(data), 1)
