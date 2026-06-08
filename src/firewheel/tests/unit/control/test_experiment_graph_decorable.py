# pylint: disable=invalid-name

import unittest

import firewheel.control.experiment_graph


class ExperimentGraphDecorableTestCase(unittest.TestCase):
    def setUp(self):
        self.inst = firewheel.control.experiment_graph.ExperimentGraphDecorable()

    def tearDown(self):
        self.inst = None

        # Reset this
        firewheel.control.experiment_graph.CACHED_DECORATOR_OBJECTS = {}

    def test_invalid_decorator(self):
        with self.assertRaises(TypeError):
            self.inst.decorate({})

    def test_method(self):
        expected_return = 42

        class Dec:
            def foo(self):
                return expected_return

        self.inst.decorate(Dec)
        result = self.inst.foo()  # pylint: disable=no-member

        undec = Dec()
        undec_result = undec.foo()

        self.assertEqual(result, undec_result)
        self.assertEqual(result, expected_return)

    def test_method_explicit_descriptor(self):
        expected_return = 42

        class Dec:
            class FooClass:
                # pylint: disable=redefined-builtin
                def __get__(self, obj, type=None):  # noqa: A002
                    return lambda: expected_return

            foo = FooClass()

        self.inst.decorate(Dec)
        result = self.inst.foo()  # pylint: disable=no-member

        undec = Dec()
        undec_result = undec.foo()

        self.assertEqual(result, undec_result)
        self.assertEqual(result, expected_return)

    def test_decorator_data_attributes(self):
        expected_return = 42

        class Dec:
            def __init__(self):
                self.my_return = expected_return

            def foo(self):
                return self.my_return

        self.inst.decorate(Dec)
        result = self.inst.foo()  # pylint: disable=no-member

        undec = Dec()
        undec_result = undec.foo()

        self.assertEqual(result, undec_result)
        self.assertEqual(result, expected_return)

    def test_decorator_class_data_attribute(self):
        class Dec:
            my_return = 45

            def foo(self):
                return self.my_return

        self.inst.decorate(Dec)
        result = self.inst.foo()  # pylint: disable=no-member

        undec = Dec()
        undec_result = undec.foo()

        self.assertEqual(result, undec_result)
        self.assertEqual(result, Dec.my_return)

    def test_decorator_init_args(self):
        class Dec:
            def __init__(self, arg1, arg2="foo"):
                self.arg1 = arg1
                self.arg2 = arg2

            def get_arg1(self):
                return self.arg1

            def get_arg2(self):
                return self.arg2

        expected_arg1 = 42
        expected_arg2 = "bar"

        self.inst.decorate(
            Dec, init_args=[expected_arg1], init_kwargs={"arg2": expected_arg2}
        )
        result1 = self.inst.get_arg1()  # pylint: disable=no-member
        result2 = self.inst.get_arg2()  # pylint: disable=no-member

        self.assertEqual(result1, expected_arg1)
        self.assertEqual(result2, expected_arg2)

    def test_decorator_inheritance(self):
        expected_return = 42

        class Dec:
            def foo(self):
                return expected_return

        class DecChild(Dec):
            def foo(self):
                return expected_return + 2

            def bar(self):
                return expected_return

        self.inst.decorate(DecChild)
        result1 = self.inst.foo()  # pylint: disable=no-member
        result2 = self.inst.bar()  # pylint: disable=no-member

        undec = DecChild()
        undec_result1 = undec.foo()
        undec_result2 = undec.bar()

        self.assertEqual(result1, undec_result1)
        self.assertEqual(result2, undec_result2)
        self.assertEqual(result1, expected_return + 2)
        self.assertEqual(result2, expected_return)

    def test_data_descriptor(self):
        class Dec:
            class FooClass:
                def __init__(self):
                    self.ctr = 0

                # pylint: disable=redefined-builtin
                def __get__(self, obj, type=None):  # noqa: A002
                    self.ctr += 1
                    return self.ctr

                def __set__(self, obj, val):
                    raise NotImplementedError()

                def __delete__(self, instance):
                    raise NotImplementedError()

            foo = FooClass()

        undec_inst = Dec()
        # If we correctly call __get__ and don't use a static value then 2
        # accesses to foo should have different values.
        self.assertNotEqual(undec_inst.foo, undec_inst.foo)

        # Confirm the sequence of values is a class attribute.
        undec_inst2 = Dec()
        # Not a typo: This should access undec_inst, not undec_inst2.
        previous = undec_inst.foo
        self.assertEqual(undec_inst2.foo, previous + 1)

        self.inst.decorate(Dec)
        self.assertTrue(
            isinstance(self.inst.foo, Dec.FooClass)
        )  # pylint: disable=no-member
        # This is actually a fail comparison--these should be class refs, not
        # the probably intended integers.
        self.assertEqual(self.inst.foo, self.inst.foo)  # pylint: disable=no-member

    # Similar to test_data_descriptor, but implemented as a property.
    def test_property(self):
        class Dec:
            def __init__(self):
                self.ctr = 0

            def g(self):
                self.ctr += 1
                return self.ctr

            def s(self, val):
                raise NotImplementedError()

            def d(self):
                raise NotImplementedError()

            foo = property(g, s, d, "I'm the 'foo' property.")

        undec_inst = Dec()
        self.assertNotEqual(undec_inst.foo, undec_inst.foo)
        self.assertEqual(undec_inst.foo + 1, undec_inst.foo)

        undec_inst2 = Dec()
        previous = undec_inst.foo
        self.assertNotEqual(undec_inst2.foo, previous + 1)

        self.inst.decorate(Dec)
        # Now access to self.inst.foo will give a 'property' object.
        # This is the documented behavior
        self.assertEqual(self.inst.foo, self.inst.foo)  # pylint: disable=no-member
        self.assertTrue(
            isinstance(self.inst.foo, property)
        )  # pylint: disable=no-member

    # This ends up testing both conflict resolution and class methods.
    # Class methods are unsupported (or more closely somewhat incorrectly
    # supported).
    # Conflict resolution is expected to work.
    def test_decorator_eq(self):
        class Dec:
            def __init__(self, a):
                self.a = a

            def __eq__(self, other):
                return self.a == other.a

        def resolve_conflict(entry_name, decorator_entry, decoratee_entry):
            if entry_name == "__eq__":
                return decorator_entry
            return decoratee_entry

        inst2 = firewheel.control.experiment_graph.ExperimentGraphDecorable()
        # Decorator is unset; use Python default `__eq__`
        self.assertFalse(self.inst == inst2)
        self.assertIs(self.inst.__eq__(inst2), NotImplemented)

        self.inst.decorate(Dec, init_args=[42], conflict_handler=resolve_conflict)
        inst2.decorate(Dec, init_args=[42], conflict_handler=resolve_conflict)
        # Python "dunder methods" (e.g., `__eq__`) are looked up on the
        # instance's type, rather than via traditional instance
        # attribute lookup. For example:
        #     self.inst == inst2
        # is equivalent to:
        #     type(self.inst).__eq__(self.inst, inst2)
        #
        # Because our decorators do not handle class methods--everything
        # is mapped to an instance method--comparisons of this nature
        # should still fail.
        self.assertFalse(self.inst == inst2)

    def test_is_decorated_by(self):
        class Dec:
            pass

        class Dec2:
            pass

        self.assertFalse(self.inst.is_decorated_by(Dec))
        self.inst.decorate(Dec)
        self.assertTrue(self.inst.is_decorated_by(Dec))
        self.assertFalse(self.inst.is_decorated_by(Dec2))
        self.inst.decorate(Dec2)
        self.assertTrue(self.inst.is_decorated_by(Dec2))
        self.assertTrue(self.inst.is_decorated_by(Dec))

    def test_double_decorate(self):
        class Dec:
            pass

        self.inst.decorate(Dec)
        with self.assertRaises(
            firewheel.control.experiment_graph.DecoratorConflictError
        ):
            self.inst.decorate(Dec)

    def test_unhandled_name_conflict(self):
        class Dec:
            foo = 42

        class Dec2:
            foo = 43

        self.inst.decorate(Dec)
        with self.assertRaises(
            firewheel.control.experiment_graph.DecoratorConflictError
        ):
            self.inst.decorate(Dec2)

    def test_vertex_is_decorable(self):
        expected_return = 42

        class Dec:
            def foo(self):
                return expected_return

        v = firewheel.control.experiment_graph.Vertex(
            firewheel.control.experiment_graph.ExperimentGraph()
        )
        self.assertTrue(
            isinstance(v, firewheel.control.experiment_graph.ExperimentGraphDecorable)
        )

        v.decorate(Dec)
        result = v.foo()  # pylint: disable=no-member
        self.assertEqual(result, expected_return)

    def test_edge_is_decorable(self):
        expected_return = 42

        class Dec:
            def foo(self):
                return expected_return

        g = firewheel.control.experiment_graph.ExperimentGraph()
        v1 = firewheel.control.experiment_graph.Vertex(g)
        v2 = firewheel.control.experiment_graph.Vertex(g)
        e = firewheel.control.experiment_graph.Edge(v1, v2)
        self.assertTrue(
            isinstance(e, firewheel.control.experiment_graph.ExperimentGraphDecorable)
        )

        e.decorate(Dec)
        result = e.foo()  # pylint: disable=no-member
        self.assertEqual(result, expected_return)
