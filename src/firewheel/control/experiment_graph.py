"""
This module contains numerous classes related to the FIREWHEEL experiment graph.

Attributes:
    CACHED_DECORATOR_OBJECTS (dict): This module-level dictionary enables the caching of
        each MC Object used and the methods/attributes (e.g., :py:func:`dir`) of those objects.
        By caching this, the performance is greatly increased due to fewer calls to
        :py:func:`dir`.
"""

import types
import pprint
import random
import inspect
import logging
from multiprocessing import Queue, Process

import networkx as nx

from firewheel.lib.log import Log


class AbstractPlugin:
    """
    This class will be inherited by all model component plugin files.
    """

    def __init__(self, graph, log):
        """
        Initialize the plugin.

        Args:
            graph (ExperimentGraph): The experiment graph in which the plugin will execute.
            log (logging.Logger): A log the plugin can use.
        """
        self.g = graph  # pylint: disable=invalid-name
        self.log = log

    def get_experiment_graph(self):
        """
        Returns:
            ExperimentGraph: The experiment graph.
        """
        return self.g


class NoSuchVertexError(Exception):
    """
    Occurs when the :py:class:`Vertex` does not exist.
    """


class DecoratorConflictError(Exception):
    """
    If there are two decorators which interfere with each other this exception is used.
    """


class DecorationError(Exception):
    """
    This exception is used if there is an error decorating a :py:class:`Vertex`.
    """


class IncorrectConflictHandlerError(Exception):
    """
    This exception is intended to be thrown by decorator conflict handlers when
    the entry name is not one that the handler is intended to handle.
    """


# This module-level dictionary enables the caching of each MC Object used
# and the methods/attributes (e.g. ``dir()`` of those objects. By cacheing
# this, the performance is greatly increased due to fewer calls to ``dir()``.
CACHED_DECORATOR_OBJECTS = {}


class ExperimentGraphDecorable:
    """
    A per-instance decorable object. This permits the attributes and interface
    to change for instances of this object, with the changes limited to the
    particular instance that is "decorated".

    Because this affects the instance level, there are some limitations:

    - Class methods and attributes in the decorator become instance methods
      and attributes (respectively) in the decorated instance.
    - Method descriptors are supported, with the caveat that they are reduced
      to basic methods. That is, the method descriptor's ``__get__`` function is
      called with the merged instance, and the result becomes an instance
      method.
    - Descriptors (and properties) are handled as class attributes.
      This breaks the "descriptor-ness" of the attributes--lookups simply return
      the actual descriptor object.
    - Using a descriptor with any method in the
      :py:attr:`skip_set <firewheel.control.experiment_graph.ExperimentGraphDecorable.skip_set>`
      may not function as expected.

    Note:
        Some common methods such as ``__eq__`` are actually class methods. This
        results in decorators being unable to affect operators such as ``==``.

    Names in the decorator and decoratee instance may conflict. If these occur
    at the class-level in the decorator, these conflicts may be resolved by
    providing the decorate function with a ``conflict_handler``. This is a
    callable taking 3 positional arguments: ``entry_name``, ``decorator_value``,
    ``current_instance_value``, where the values are the values of the attribute
    at ``entry_name``. The callable must return the value for the merged attribute
    if the conflict handler found an appropriate way to deconflict, otherwise
    it should raise an :py:exc:`IncorrectConflictHandlerError`, signaling that
    another conflict handler was likely intended to be used for the given
    attribute.

    The merge process also ignores some built-in attributes by name to avoid
    always causing merge conflicts. Specifically, these are defined in
    :py:attr:`skip_set <firewheel.control.experiment_graph.ExperimentGraphDecorable.skip_set>`.

    Note:
        Notably, the only built-in methods which we expect users to modify are
        ``__str__`` and ``__repr__``. Any modification of other built-in types
        (e.g., ``__hash__`` or ``__eq__``) may not function as expected.


    Finally, once the methods/attributes have been merged into the instance, the
    decorator's ``__init__`` method is called. This method is given the merged
    instance, so any values the decorator expects to initialize should behave
    normally from the perspective of the decorator's code. Arguments for the
    decorator's ``__init__`` may be passed to the decorate function, with positional
    arguments as a list to the init_args keyword and keyword arguments as a
    dictionary to the ``init_kwargs`` keyword.

    The behaviors outlined here are expected to combine to allow decorators to
    be implemented as a normal class.

    Examples:
        **Merging Example**

        Current instance defines ``common_method`` as (this could be in some
        already-applied decorator):

        .. code-block:: python

            class Foo:
                def common_method(self):
                    return 42

        and the decorator being applied defines ``common_method`` as:

        .. code-block:: python

            class Bar:
                def common_method(self):
                    return 50

        If we want the merge to use ``Bar``'s definition of ``common_method`` over any
        other definition (as a way to simulate inheritance) we could provide
        the following function as the value of ``conflict_handler``:

        .. code-block:: python

            def handle_conflict(entry_name, decorator_value, instance_value):
                if entry_name == 'common_method':
                    return Bar.common_method
                raise IncorrectConflictHandlerError
    """

    def __init__(self):
        """
        Initialize an empty list of decorators and also a list of methods
        to skip.

        Attributes:
            decorators (set): A set of decorators (initially empty).
            skip_set (set): A set of methods to skip/ignore.
                Entries are in this list for various reasons. All are "built-ins" in
                Python classes. None are of type ``types.BuiltinMethodType``, since we can
                skip those more generically. Some are dictionaries, others are type
                ``type``, and some are ``method_descriptor``'s. A ``method_descriptor``
                defines some object that is not implemented in Python source (e.g.,
                it is in C). We do not want to skip all of these, because we may
                actually want to merge some objects that are implemented in C (so we
                put them in the skip list by name instead). Reference:
                https://stackoverflow.com/q/15512183.
                There are also ``wrapper_descriptor``'s, with similar reasoning to
                ``method_descriptors``.
                Primarily, this list includes most built-in methods that FIREWHEEL
                users are unlikely to use and, therefore, can be ignored as they
                will always be left alone. By ignoring these built-in methods
                we can greatly improve performance of decorating a :py:class:`Vertex`.
                Notably, the only built-in methods which we expect users to modify
                are ``__str__`` and ``__repr__``.
                Perhaps a starting document is:
                https://docs.python.org/3/howto/descriptor.html
            cached_self_dir (set): A set of methods/attributes for the current object.
                by initializing this set in the ``__init__`` function and then adding
                to it with each decoration, we can reduce the number of calls to
                :py:func:`dir`, which is an expensive operation.


        """
        self.decorators = set()
        self.conflict_handlers = []

        # We want to ignore most of the built-in methods for functionality reasons
        # and performance reasons.
        self.skip_set = {
            "__class__",
            "__doc__",
            "__delattr__",
            "__dict__",
            "__dir__",
            "__eq__",
            "__firstlineno__",  # New in 3.13
            "__format__",
            "__ge__",
            "__getattribute__",
            "__getstate__",
            "__gt__",
            "__hash__",
            "__init__",
            "__init_subclass__",
            "__le__",
            "__lt__",
            "__module__",
            "__ne__",
            "__new__",
            "__reduce__",
            "__reduce_ex__",
            "__setattr__",
            "__sizeof__",
            "__static_attributes__",  # New in 3.13
            "__subclasshook__",
            "__weakref__",
        }

        # Initialize the current object's methods/attributes
        self.cached_self_dir = set(dir(self))

    # pylint: disable=unnecessary-dunder-call
    def decorate(
        self, decorator_class, init_args=None, init_kwargs=None, conflict_handler=None
    ):
        """
        Each graph :py:class:`Vertex` and :py:class:`Edge` are a layered stack of
        Python objects where each layer is a python decorator.
        Class functions can then be called on
        all the objects. Using this methodology, model component objects can be
        mixed and matched to create the desired :py:class:`Vertex`/:py:class:`Edge`.
        This creates an easy way to build complicated experiments with modular code.
        Decoration can be used to:

        * Provide specific :py:class:`Vertex`/:py:class:`Edge` functions.
        * Specify images or VM Resources
        * Leverage software/configuration available in other Model Components.

        Here is an example of a potential model component object stack::

            Vertex("host.acme.com")
            |
            -> VMEndpoint()
            |   - run_executable()
            |   - drop_file()
            |   - connect()
            |
            --> LinuxHost()
            |    - configure_ips()
            |    - set_hostname()
            |
            ---> UbuntuHost()
            |     - install_debs()
            |
            ----> Ubuntu1604Server()

        The :py:class:`Vertex` starts with only a name, but as it is decorated by various other
        objects, it gains new properties and methods which can be leveraged.

        There are two ways to build up this model component object stack. You
        can use explicit decoration, in which all components are added explicitly,
        as shown below::

            server = Vertex("host.acme.com")
            server.decorate(VMEndpoint)
            server.decorate(LinuxHost)
            server.decorate(UbuntuHost)
            server.decorate(Ubuntu1604Server)

        Alternatively, you can use dependency decoration and only call decorate
        on the last object in the stack (assuming it uses ``@require_class`` on the
        previous layers)::

            server = Vertex("host.acme.com")
            server.decorate(Ubuntu1604Server)

        The decorate method is necessary to decorate graph :py:class:`Vertices <Vertex>` or
        :py:class:`Edges <Edge>` with additional model component objects.
        It is important to note that we make
        class attributes into instance attributes (as the general case for data
        and functions). This could impact behavior, especially for assumptions
        with respect to class data attributes.

        Additionally, we expect that users will **NOT** modify most built-in methods
        which were defined in the
        :py:attr:`skip_set <firewheel.control.experiment_graph.ExperimentGraphDecorable.skip_set>`.
        We only assume that users have potentially modified ``__str__`` and ``__repr__``.
        If either of these methods has been modified (e.g. not equal to the
        default :py:class:`object` implementation, then we will need a conflict handler.

        Note:
            We are using :py:func:`getattr` rather than :py:func:`inspect.getattr_static`.
            If a MC Object sets either ``__str__`` or ``__repr__``
            using Python descriptors, that code will be executed and may differ.
            This decision was made because 1) The chances of using descriptor to set
            one of these methods is rare when creating a FIREWHEEL Model Component Object
            and 2) :py:func:`getattr` is significantly faster than
            :py:func:`inspect.getattr_static`.
            The performance hit from using :py:mod:`inspect` is dramatic when you consider each
            :py:class:`Vertex` may be decorated numerous times and there may be thousands of
            :py:class:`Vertices <Vertex>`/:py:class:`Edges <Edge>` in the graph.

            Here is a :py:mod:`timeit` comparison:

            >>> import timeit
            >>> timeit.timeit("getattr(object, '__str__')")
            0.1993947122246027
            >>> timeit.timeit("inspect.getattr_static(object, '__str__')", setup="import inspect")
            3.008564186282456

        This method also uses a module-level dictionary of all the MC objects
        and their methods/attributes
        (:py:data:`CACHED_DECORATOR_OBJECTS
        <firewheel.control.experiment_graph.CACHED_DECORATOR_OBJECTS>`).
        This is a performance improvement as :py:func:`dir()` is an expensive
        operation and will no longer need to be called for each instance of the same object.
        This will only have minor memory impacts as most experiments use only a handful
        of different MC Objects types.

        Args:
            decorator_class (object): The model component object which will
                decorate the :py:class:`Vertex`/:py:class:`Edge`.
            init_args (list): Any initial arguments required by the `decorator_class`.
            init_kwargs (dict): Any initial keyword arguments required by the
                ``decorator_class``.
            conflict_handler (func): A conflict handler callable. This is described in
                more detail in the class documentation.

        Raises:
            TypeError: If ``decorator_class`` is not a class.
            DecoratorConflictError: If there is a conflict between two objects
                in the stack.
        """
        if not init_args:
            init_args = []

        if not init_kwargs:
            init_kwargs = {}

        if self.is_decorated_by(decorator_class):
            raise DecoratorConflictError(
                f"Instance is already decorated by {decorator_class}"
            )

        if not inspect.isclass(decorator_class):
            raise TypeError("Decorator must be a class.")

        # We keep a module-level dictionary of all the MC objects and their methods/attributes.
        # This is a performance improvement as ``dir()`` is an expensive operation and will
        # no longer need to be called for each instance of the same object.
        # This will only have minor memory impacts as most experiments use less than
        # 100 different MC Objects.
        try:
            decorator_entries = CACHED_DECORATOR_OBJECTS[decorator_class.__name__]
        except KeyError:
            CACHED_DECORATOR_OBJECTS[decorator_class.__name__] = set(
                dir(decorator_class)
            )
            decorator_entries = CACHED_DECORATOR_OBJECTS[decorator_class.__name__]

        decorator_entries -= self.skip_set

        if conflict_handler is not None:
            # add to beginning of list so it gets used first
            self.conflict_handlers.insert(0, conflict_handler)

        for entry in decorator_entries:
            if entry in {"__str__"}:
                # We want to ensure that these more common dunder methods have not been customized.
                # If they have been, then we will need a conflict handler.
                #
                # It is important to note that we are using `getattr` rather than
                # `inspect.getattr_static`. If an Object sets one of these methods
                # using descriptor's that code will be executed and may differ.
                # This decision was made because 1. The chances of using descriptor to set
                # one of these methods is rare when creating a FIREWHEEL Model Component Object
                # and 2. `getattr` is significantly faster than `inspect.getattr_static`.
                # The performance hit from using inspect is dramatic when you consider each
                # Vertex may be decorated numerous times and there may be thousands of
                # Verticies/Edges in the graph.
                #
                # Here is a `timeit` comparison from Python 3.8:
                # >>> import timeit
                # >>> timeit.timeit("getattr(object, '__str__')")
                # 0.10375281400047243
                # >>> timeit.timeit(
                # ... "inspect.getattr_static(object, '__str__')",
                # ... setup="import inspect"
                # ... )
                # 1.9434310980141163
                #
                # Now that we use `getattr` to identify an object's attribute, we need to compare
                # it to a "default" object. There are a few methods for doing this:
                # `object.__getattribute__(object, entry)`, `getattr(object, entry)`, and
                # `object.<entry>`. In Python 3.12, the return value of
                # `object.__getattribute__(object, entry)` changed.
                #
                # Python 3.12
                # >>> object.__getattribute__(object, "__str__")
                # <method-wrapper '__str__' of type object at 0x107eb41c0>
                #
                # Python 3.11
                # >>> object.__getattribute__(object, "__str__")
                # <slot wrapper '__str__' of 'object' objects>
                #
                # Therefore, we need to use one of the second methods. In this case using
                # `object.<entry>` is faster per `timeit`.
                #
                # Python 3.12
                # >>> import timeit
                # >>> timeit.timeit("getattr(object, '__str__')")
                # 0.058882773970253766
                # >>> timeit.timeit("object.__str__")
                # 0.03296143497573212
                #
                if getattr(decorator_class, entry) == object.__str__:  # noqa: PLC2801
                    continue
                self.log.debug("Default method %s changed", entry)
            elif entry in {"__repr__"}:
                if getattr(decorator_class, entry) == object.__repr__:
                    continue
                self.log.debug("Default method %s changed", entry)

            if entry == "_conflict_handlers":
                attr = inspect.getattr_static(
                    decorator_class, entry, []
                ) + inspect.getattr_static(self, entry, [])

            elif entry in self.cached_self_dir:
                handlers = (
                    self.conflict_handlers
                    + inspect.getattr_static(decorator_class, "_conflict_handlers", [])
                    + inspect.getattr_static(self, "conflict_handlers", [])
                )
                for handler in handlers:
                    try:
                        attr = handler(
                            entry,
                            inspect.getattr_static(decorator_class, entry),
                            inspect.getattr_static(self, entry),
                        )
                        if attr is None:
                            continue
                        break
                    except IncorrectConflictHandlerError:
                        pass

                else:
                    dec_names = {d.__name__ for d in self.decorators}
                    raise DecoratorConflictError(
                        f"Unable to merge '{entry}' because it occurs in one of: "
                        f"{dec_names} and '{decorator_class.__name__}'. "
                        "Please specify a conflict handler or rename the attribute."
                        " This may also occur if the attribute value is intended "
                        "to be :py:data:`None`."
                    )
            else:
                attr = decorator_class.__getattribute__(decorator_class, entry)  # noqa: PLC2801

            # It turns out that in a class, what will be considered methods
            # when instantiated are still functions internally. We must bind
            # these functions as methods to our current instance.
            # Reference: https://docs.python.org/3/howto/descriptor.html#functions-and-methods
            # Doing this try/except instead of if/then reduces time by about 13%.
            try:
                attr = types.MethodType(attr, self)
            except TypeError:
                try:
                    # Continuing with a correct descriptor implementation, we watch
                    # for explicit descriptor definitions as methods. That is,
                    # this matches the case:
                    #
                    # >>> class Dec(object):
                    # >>>     class FooClass(object):
                    # >>>         def __get__(self, obj, type=None):
                    # >>>             return lambda: print('Hello, Descriptor')
                    # >>>     Foo = FooClass()
                    #
                    # When this Dec class is instantiated, Foo is a method:
                    # >>> inst = Dec()
                    # >>> inst.Foo()
                    # Hello, Descriptor
                    #
                    # We want this way of defining a method to behave the same as a
                    # traditional "def" statement (which creates something related
                    # under the hood--read the descriptor howto linked above). That
                    # is, we want the behavior to be:
                    # >>> inst = ExperimentGraphDecorable()
                    # >>> inst.decorate(Dec)
                    # >>> inst.Foo()
                    # Hello, Descriptor
                    #
                    # The key point here is Dec.Foo is a class attribute (this makes
                    # sense as a method). So, when we try to assign Foo as an
                    # instance attribute, things don't quite work correctly. Inside,
                    # python seems to be trying to call Dec.Foo.__get__(...), but
                    # the same descriptor protocol doesn't seem to apply to the
                    # instance attribute inst.Foo. Again, this works with normal
                    # methods because they are class attributes.
                    #
                    # By implementing the descriptor protocol "layer" and setting the
                    # instance attribute appropriately, we can effectively produce a
                    # correct method assigned only to this instance. Additionally,
                    # everything (e.g. self) should be bound correctly by virtue
                    # of the parameters to __get__.
                    #
                    # One additional reference put the final pieces together:
                    # http://stackoverflow.com/questions/1325673/how-to-add-property-to-a-class-dynamically
                    #
                    # Trying for performance. In the expected majority of cases,
                    # this will cause an AttributeError. If it doesn't, we need
                    # to make sure this is a method descriptor and not a data
                    # descriptor before we actually replace attr.
                    get_attr = attr.__get__(attr, self)
                    if inspect.ismethoddescriptor(attr):
                        attr = get_attr
                except AttributeError:
                    pass
            # The use of __setattr__ and __dict__ seem to be semantically
            # equivalent here, although __setattr__ seems to be more like what
            # we are really trying to do.
            # Additionally, testing indicates __setattr__ may be 1-1.5% faster
            # in the best case than __dict__ and is significantly more
            # consistent with time for execution. __dict__ was observed to take
            # as much as 15% longer some of the time, where the variation in
            # __setattr__ appears to be 1-2%.
            setattr(self, entry, attr)

            # We want to add these attributes/methods to our set of attributes/methods
            # for the current vertex. Having this as a cached set improves performance
            # by eliminating a call to ``dir()`` for each decoration.
            # We need to catch an AttributeError because class attributes do not have
            # a ``__name__``, but methods do.
            try:
                self.cached_self_dir.add(attr.__name__)
            except AttributeError:
                self.cached_self_dir.add(entry)

        self.decorators.add(decorator_class)

        # We need to make sure attributes initialized by the decorator's
        # __init__ method are correctly handled. The best way to do this is to
        # actually call the decorator's __init__. By giving it the decoratee's
        # self, it will deal with values on the correct instance.
        init = decorator_class.__getattribute__(decorator_class, "__init__")  # noqa: PLC2801
        init(self, *init_args, **init_kwargs)

    def is_decorated_by(self, decorator_class):
        """
        Check if a :py:class:`Vertex`/:py:class:`Edge` is decorated by a particular class.

        Args:
            decorator_class (Object): The model component object to check against.

        Returns:
            bool: ``True`` if the :py:class:`Vertex`/:py:class:`Edge` was decorated
            by the passed in class, ``False`` otherwise.
        """
        return decorator_class in self.decorators

    def __getstate__(self):
        state = self.__dict__.copy()

        to_delete = []
        for key in state:
            if inspect.ismethod(state[key]):
                to_delete.append(key)
        for key in to_delete:
            del state[key]

        if "log" in state:
            state["log"] = state["log"].name

        return state

    def __setstate__(self, state):
        self.decorators = set()
        self.skip_set = state["skip_set"]
        self.cached_self_dir = set(dir(self))
        for decorator in state["decorators"]:
            self.decorate(decorator)

        if "log" in state:
            state["log"] = logging.getLogger(state["log"])

        to_delete = []
        for key, value in self.__dict__.items():
            if key not in state and not inspect.ismethod(value):
                to_delete.append(key)

        for key in to_delete:
            del self.__dict__[key]

        self.__dict__.update(state)


# pylint: disable=invalid-name
class require_class:  # noqa: N801
    """
    A Python decorator to express a dependency from one decorator to another.

    Example::

        class VMEndpoint(object):
            ...

        # A GenericRouter is always a VMEndpoint
        @require_class(VMEndpoint)
        class GenericRouter(object):
            ...
    """

    def __init__(self, required_decorator, conflict_handler=None):
        """
        Initialize the required decorator.

        Args:
            required_decorator (Object): The class which must decorate the new
                model component object.
            conflict_handler: A conflict handler callable. This is described in
                more detail in the class documentation.
        """
        self.required_decorator = required_decorator
        self.conflict_handler = conflict_handler

    def __call__(self, graph_object):
        """
        Call self as a function. This takes in the graph object to be decorated
        and ensures that the decoration happens.

        Args:
            graph_object (Object): The graph object to be decorated.

        Returns:
            Object: The newly decorated graph object.
        """
        original_init = graph_object.__init__
        req_dec = self.required_decorator
        conflict_handler = self.conflict_handler

        def assure_decorated(instance, decorator, conflict_handler):
            if not instance.is_decorated_by(decorator):
                try:
                    instance.decorate(decorator, conflict_handler=conflict_handler)
                except TypeError as exc:
                    raise DecorationError(
                        f'Unable to require class (decoration) with "{decorator.__name__}"'
                        f' before decorating with "{graph_object.__name__}".'
                        " Probably missing constructor arguments."
                        f' Please decorate with "{decorator.__name__}" before '
                        f'decorating with "{graph_object.__name__}".'
                    ) from exc

        def new_init(self, *args, **kwargs):
            assure_decorated(self, req_dec, conflict_handler)
            original_init(self, *args, **kwargs)

        if self.conflict_handler is not None:
            if hasattr(graph_object, "_conflict_handlers"):
                graph_object._conflict_handlers.append(self.conflict_handler)
            else:
                graph_object._conflict_handlers = [self.conflict_handler]

        graph_object.__init__ = new_init

        return graph_object


class Vertex(ExperimentGraphDecorable):
    """
    This class represents a FIREWHEEL-specific Vertex. It inherits from
    :py:class:`ExperimentGraphDecorable`
    and implements all the expected methods for a :py:mod:`networkx` Node.
    """

    vertex_log = Log(name="ExperimentGraphVertex").log

    def __init__(self, graph, name=None, graph_id=None):
        """
        Initialize the :py:class:`Vertex`.

        Attributes:
            g (ExperimentGraph): The graph in which the :py:class:`Vertex` should exist.
            graph_id (int): The integer representation of the :py:class:`Vertex`.
            valid (bool): If the :py:class:`Vertex` should exist in the graph
                (i.e., has not yet been deleted).
            log (firewheel.lib.log.Log): The logger to use for this :py:class:`Vertex`.
            name (str): The name of the :py:class:`Vertex`.

        Args:
            graph (ExperimentGraph): The in which the :py:class:`Vertex` should exist.
            name (str): The name of the :py:class:`Vertex`.
            graph_id (int): The integer representation of the :py:class:`Vertex`.
        """
        super().__init__()

        self.g = graph  # pylint: disable=invalid-name
        self.graph_id = self.g._add_vertex(graph_id)
        self.g.g.nodes[self.graph_id]["object"] = self
        self.valid = True

        self.log = self.vertex_log

        if name:
            self.name = name

    def get_object(self):
        """
        Get the :py:class:`Vertex` object attribute (i.e. ``self``).

        Returns:
            Vertex: This :py:class:`Vertex`.

        Raises:
            RuntimeError: If the :py:class:`Vertex` is not :py:attr:`Vertex.valid`.
        """
        if not self.valid:
            raise RuntimeError("Attempted operation on invalid Vertex instance.")
        return self.g.g.nodes[self.graph_id]["object"]

    def keys(self):
        """
        Dictionary-style access to get a list of :py:class:`Vertex` attribute keys.

        Returns:
            list: A list of :py:class:`Vertex` attributes.

        Raises:
            RuntimeError: If the :py:class:`Vertex` is not :py:attr:`Vertex.valid`.
        """
        if not self.valid:
            raise RuntimeError("Attempted operation on invalid Vertex instance.")
        return self.g.g.nodes[self.graph_id].keys()

    def __getitem__(self, key):
        """
        Dictionary-style access to read :py:class:`Vertex` attributes.

        Args:
            key (str): A key to query.

        Raises:
            RuntimeError: If the :py:class:`Vertex` is not :py:attr:`Vertex.valid`.

        Returns:
            The value of the requested attribute.
        """
        if not self.valid:
            raise RuntimeError("Attempted operation on invalid Vertex instance.")
        return self.g.g.nodes[self.graph_id][key]

    def __setitem__(self, key, value):
        """
        Dictionary-style access to set a :py:class:`Vertex` attributes.

        Args:
            key (str): An attribute key.
            value (Any): The value of the attribute.

        Raises:
            RuntimeError: If the :py:class:`Vertex` is not :py:attr:`Vertex.valid`.
        """
        if not self.valid:
            raise RuntimeError("Attempted operation on invalid Vertex instance.")
        self.g.g.nodes[self.graph_id][key] = value

    def has(self, key):
        """
        Dictionary-style query for the presence of a key.

        Args:
            key (str): A key to query.

        Returns:
            bool: If the key exists.

        Raises:
            RuntimeError: If the :py:class:`Vertex` is not :py:attr:`Vertex.valid`.
        """
        if not self.valid:
            raise RuntimeError("Attempted operation on invalid Vertex instance.")
        return key in self.g.g.nodes[self.graph_id]

    def __contains__(self, key):
        """
        Check if the :py:class:`Vertex` has a particular attribute.

        Args:
            key (str): The attribute to query.

        Returns:
            bool: Tue, if the key exists, ``False`` otherwise.

        Raises:
            RuntimeError: If the :py:class:`Vertex` is not :py:attr:`Vertex.valid`.
        """
        if not self.valid:
            raise RuntimeError("Attempted operation on invalid Vertex instance.")
        return self.has(key)

    def get_neighbors(self):
        """
        Get an iterator of all of this :py:class:`Vertex`'s neighbors.

        Returns:
            VertexIterator: All the :py:class:`Vertex` instances that this
            :py:class:`Vertex` is connected to.

        Raises:
            RuntimeError: If the :py:class:`Vertex` is not :py:attr:`Vertex.valid`.
        """
        if not self.valid:
            raise RuntimeError("Attempted operation on invalid Vertex instance.")
        return VertexIterator(self.g, self.g.g.neighbors(self.graph_id))

    def __str__(self):
        """
        Provide a nicely formatted string describing the :py:class:`Vertex`.

        Returns:
            str: A nicely formatted string describing the :py:class:`Vertex`.

        Raises:
            RuntimeError: If the :py:class:`Vertex` is not :py:attr:`Vertex.valid`.
        """
        if not self.valid:
            raise RuntimeError("Attempted operation on invalid Vertex instance.")
        return pprint.pformat(self.g.g.nodes[self.graph_id])

    def __eq__(self, other):
        """
        Determine if two :py:class:`Vertex` instances are the same. Equality is based
        on having the same graph and the same ``graph_id``. This function also
        verifies that itself and another are of type :py:class:`Vertex` and are
        :py:attr:`Vertex.valid`.

        Args:
            other (Vertex): The other :py:class:`Vertex`.

        Returns:
            bool: ``True`` if they are the same, ``False`` otherwise.

        Raises:
            RuntimeError: If either :py:class:`Vertex` is not :py:attr:`Vertex.valid`.
        """
        if not isinstance(self, Vertex) or not isinstance(other, Vertex):
            return NotImplemented
        if not self.valid or not other.valid:
            raise RuntimeError("Attempted operation on invalid Vertex instance.")
        if self.g == other.g and self.graph_id == other.graph_id:
            return True
        return False

    def __ne__(self, other):
        """
        Determine if two :py:class:`Vertex` instances are not equal. Inequality is based
        on the opposite of the :py:meth:`Vertex.__eq__()` method.
        This function also verifies that itself and another are of type :py:class:`Vertex` and
        are :py:attr:`Vertex.valid`.

        Args:
            other (Vertex): The other :py:class:`Vertex`.

        Returns:
            bool: ``True`` if they are not the same, ``False`` otherwise.

        Raises:
            RuntimeError: If either :py:class:`Vertex` is not :py:attr:`Vertex.valid`.
        """
        if not isinstance(self, Vertex) or not isinstance(other, Vertex):
            return NotImplemented
        if not self.valid or not other.valid:
            raise RuntimeError("Attempted operation on invalid Vertex instance.")
        return not self.__eq__(other)

    def __hash__(self):
        """
        Get the hash of a tuple containing the :py:class:`ExperimentGraph` and
        the :py:attr:`Vertex.graph_id`.

        Returns:
            int: The hash of a tuple containing the :py:class:`ExperimentGraph` and
            the :py:attr:`Vertex.graph_id`.
        """
        return hash((self.g, self.graph_id))

    def __delitem__(self, key):
        """
        Remove a :py:class:`Vertex` attribute based on a key.

        Args:
            key (str): An attribute/property to delete.

        Raises:
            RuntimeError: If the :py:class:`Vertex` is not :py:attr:`Vertex.valid`.
        """
        if not self.valid:
            raise RuntimeError("Attempted operation on invalid Vertex instance.")
        del self.g.g.nodes[self.graph_id][key]

    def delete(self):
        """
        Remove this :py:class:`Vertex` from the ExperimentGraph.
        This sets the :py:attr:`Vertex.valid` property to ``False``.
        """
        self.g.g.remove_node(self.graph_id)
        self.valid = False

    def get_degree(self):
        """
        Get the degree of the :py:class:`Vertex`. That is, the number of
        :py:class:`Edges <Edge>` that are incident to the :py:class:`Vertex`.

        Returns:
            int: The degree of the :py:class:`Vertex`.

        Raises:
            RuntimeError: If the :py:class:`Vertex` is not :py:attr:`Vertex.valid`.
        """
        if not self.valid:
            raise RuntimeError("Attempted operation on invalid Vertex instance.")
        return self.g.g.degree([self.graph_id])[self.graph_id]

    def __iter__(self):
        """
        Iterate over the :py:class:`Vertex`.

        Returns:
            An iterator that iterates over the :py:class:`Vertex` properties.
        """
        return iter(self.g.g.nodes[self.graph_id])

    def __lt__(self, other):
        """
        Determine if a :py:class:`Vertex` is less than another :py:class:`Vertex`.
        The comparison is based on the :py:attr:`Vertex.graph_id`.
        This function also verifies that itself and another are of type
        :py:class:`Vertex` and are :py:attr:`Vertex.valid`.

        Args:
            other (Vertex): The other :py:class:`Vertex`.

        Returns:
            bool: ``True`` if self is less than other, ``False`` otherwise.

        Raises:
            RuntimeError: If either :py:class:`Vertex` is not :py:attr:`Vertex.valid`.
        """
        if not isinstance(self, Vertex) or not isinstance(other, Vertex):
            return NotImplemented
        if not self.valid or not other.valid:
            raise RuntimeError("Attempted operation on invalid Vertex instance.")
        return self.graph_id < other.graph_id

    def __le__(self, other):
        """
        Determine if a :py:class:`Vertex` is less than or equal to another :py:class:`Vertex`.
        The comparison is based on the :py:attr:`Vertex.graph_id`.
        This function also verifies that itself
        and another are of type :py:class:`Vertex` and are :py:attr:`Vertex.valid`.

        Args:
            other (Vertex): The other :py:class:`Vertex`.

        Returns:
            bool: ``True`` if self is less than or equal to other, ``False`` otherwise.

        Raises:
            RuntimeError: If either :py:class:`Vertex` is not :py:attr:`Vertex.valid`.
        """
        if not isinstance(self, Vertex) or not isinstance(other, Vertex):
            return NotImplemented
        if not self.valid or not other.valid:
            raise RuntimeError("Attempted operation on invalid Vertex instance.")
        return self < other or self == other

    def __gt__(self, other):
        """
        Determine if a :py:class:`Vertex` is greater than another :py:class:`Vertex`.
        The comparison is based on the :py:attr:`Vertex.graph_id`.
        This function also verifies that itself
        and another are of type :py:class:`Vertex` and are :py:attr:`Vertex.valid`.

        Args:
            other (Vertex): The other :py:class:`Vertex`.

        Returns:
            bool: ``True`` if self is greater than other, ``False`` otherwise.

        Raises:
            RuntimeError: If either :py:class:`Vertex` is not :py:attr:`Vertex.valid`.
        """
        if not isinstance(self, Vertex) or not isinstance(other, Vertex):
            return NotImplemented
        if not self.valid or not other.valid:
            raise RuntimeError("Attempted operation on invalid Vertex instance.")
        return self.graph_id > other.graph_id

    def __ge__(self, other):
        """
        Determine if a :py:class:`Vertex` is greater than or equal to another :py:class:`Vertex`.
        The comparison is based on the :py:attr:`Vertex.graph_id`.
        This function also verifies that itself
        and another are of type :py:class:`Vertex` and are :py:attr:`Vertex.valid`.

        Args:
            other (Vertex): The other :py:class:`Vertex`.

        Returns:
            bool: ``True`` if self is greater than or equal to other, ``False`` otherwise.

        Raises:
            RuntimeError: If either :py:class:`Vertex` is not :py:attr:`Vertex.valid`.
        """
        if not isinstance(self, Vertex) or not isinstance(other, Vertex):
            return NotImplemented
        if not self.valid or not other.valid:
            raise RuntimeError("Attempted operation on invalid Vertex instance.")
        return self > other or self == other


class Edge(ExperimentGraphDecorable):
    """
    This class represents a FIREWHEEL-specific :py:class:`Edge`.
    It inherits from :py:class:`ExperimentGraphDecorable`
    and implements all the expected methods for a :py:mod:`networkx` Edge.
    """

    edge_log = Log(name="ExperimentGraphEdge").log

    def __init__(self, source_vertex, destination_vertex):
        """
        Initialize the :py:class:`Edge`.

        Attributes:
            source (Vertex): The source :py:class:`Vertex` for this :py:class:`Edge`.
            destination (Vertex): The destination :py:class:`Vertex` for
                this :py:class:`Edge`.
            valid (bool): If the :py:class:`Edge` should exist in the graph
                (i.e., has not yet been deleted).
            log (firewheel.lib.log.Log): The logger to use for this :py:class:`Edge`.

        Args:
            source_vertex (Vertex): The source :py:class:`Vertex` for this :py:class:`Edge`.
            destination_vertex (Vertex): The destination :py:class:`Vertex` for
                this :py:class:`Edge`.

        Raises:
            TypeError: If either the source or destination are not a :py:class:`Vertex`.
            ValueError: If the :py:class:`Vertices <Vertex>` are not in the same graph or they
                are not :py:attr:`Edge.valid`.
        """
        super().__init__()

        self.source = source_vertex
        if not isinstance(self.source, Vertex):
            raise TypeError("source is not a Vertex.")
        self.destination = destination_vertex
        if not isinstance(self.destination, Vertex):
            raise TypeError("destination is not a Vertex.")

        if self.source.g != self.destination.g:
            raise ValueError("Given vertices do not belong to the same graph.")

        if not self.source.valid:
            raise ValueError("source Vertex is not valid.")
        if not self.destination.valid:
            raise ValueError("destination Vertex is not valid.")

        self.source.g._add_edge(self.source.graph_id, self.destination.graph_id)
        self.source.g.g.adj[self.source.graph_id][self.destination.graph_id][
            "object"
        ] = self
        self.valid = True

        self.log = self.edge_log

    def get_object(self):
        """
        Get the :py:class:`Edge` object attribute (i.e. self).

        Returns:
            Edge: This :py:class:`Edge`.

        Raises:
            RuntimeError: If the :py:class:`Edge` is not :py:attr:`Edge.valid`.
        """
        if not self.valid:
            raise RuntimeError("Attempted operation on invalid Edge instance.")
        return self.source.g.g.adj[self.source.graph_id][self.destination.graph_id][
            "object"
        ]

    def __getitem__(self, key):
        """
        Dictionary-style access to read :py:class:`Edge` attributes.

        Args:
            key (str): A key to query.

        Raises:
            RuntimeError: If the :py:class:`Edge` is not :py:attr:`Edge.valid`.

        Returns:
            Edge: The :py:class:`Edge` matching the key.
        """
        if not self.valid:
            raise RuntimeError("Attempted operation on invalid Edge instance.")
        return self.source.g.g.adj[self.source.graph_id][self.destination.graph_id][key]

    def __setitem__(self, key, value):
        """
        Dictionary-style access to set a :py:class:`Edge` attributes.

        Args:
            key (Any): An attribute key.
            value (Any): The value of the attribute.

        Raises:
            RuntimeError: If the :py:class:`Edge` is not :py:attr:`Edge.valid`.
        """
        if not self.valid:
            raise RuntimeError("Attempted operation on invalid Edge instance.")
        source_id, destination_id = self.source.graph_id, self.destination.graph_id
        self.source.g.g.adj[source_id][destination_id][key] = value

    def __delitem__(self, key):
        """
        Remove a :py:class:`Edge` attribute based on a key.

        Args:
            key (str): An attribute/property to delete.

        Raises:
            RuntimeError: If the :py:class:`Edge` is not :py:attr:`Edge.valid`.
        """
        if not self.valid:
            raise RuntimeError("Attempted operation on invalid Edge instance.")
        del self.source.g.g.adj[self.source.graph_id][self.destination.graph_id][key]

    def has(self, key):
        """
        Dictionary-style query for the presence of a key.

        Args:
            key (str): A key to query.

        Returns:
            bool: If the key exists.

        Raises:
            RuntimeError: If the :py:class:`Edge` is not :py:attr:`Edge.valid`.
        """
        if not self.valid:
            raise RuntimeError("Attempted operation on invalid Edge instance.")
        return (
            key in self.source.g.g.adj[self.source.graph_id][self.destination.graph_id]
        )

    def __contains__(self, key):
        """
        Check if the :py:class:`Edge` has a particular attribute.

        Args:
            key (str): The attribute to query.

        Returns:
            bool: Tue, if the key exists, ``False`` otherwise.

        Raises:
            RuntimeError: If the :py:class:`Edge` is not :py:attr:`Edge.valid`.
        """
        if not self.valid:
            raise RuntimeError("Attempted operation on invalid Edge instance.")
        return self.has(key)

    def __eq__(self, other):
        """
        Determine if two :py:class:`Edges <Edge>` are the same. Equality is based
        on having the same source and the same destination. :py:class:`Edges <Edge>`
        are not directed, so we are equal even if the direction is reversed.
        This function also verifies that itself and another are of type :py:class:`Edge`
        and are :py:attr:`Edge.valid`.

        Args:
            other (Edge): The other :py:class:`Edge`.

        Returns:
            bool: ``True`` if they are the same, ``False`` otherwise.

        Raises:
            RuntimeError: If either :py:class:`Edge` is not :py:attr:`Edge.valid`.
        """
        if not isinstance(self, Edge) or not isinstance(other, Edge):
            return False
        if not self.valid or not other.valid:
            raise RuntimeError("Attempted operation on invalid Edge instance.")
        # Edges are not directed, so we are equal even if the direction is
        # reversed.
        if self.source == other.source and self.destination == other.destination:
            return True
        if self.source == other.destination and self.destination == other.source:
            return True
        return False

    def __ne__(self, other):
        """
        Determine if two :py:class:`Edges <Edge>` are not equal. Inequality is based
        on the opposite of the `__eq__()` method.
        This function also verifies that itself and another are of type :py:class:`Edge` and
        are :py:attr:`Edge.valid`.

        Args:
            other (Edge): The other :py:class:`Edge`.

        Returns:
            bool: ``True`` if they are not the same, ``False`` otherwise.

        Raises:
            RuntimeError: If either :py:class:`Edge` is not :py:attr:`Edge.valid`.
        """
        if not isinstance(self, Edge) or not isinstance(other, Edge):
            return True
        if not self.valid or not other.valid:
            raise RuntimeError("Attempted operation on invalid Edge instance.")
        return not self.__eq__(other)

    def __hash__(self):
        """
        Get the hash of a tuple containing the hash of the destination and a hash
        of the source.

        Returns:
            int: The hash of a tuple containing the hash of the destination and
            a hash of the source.
        """
        # Edges are not directed, so hash to the same value if we just appear
        # to go the opposite direction.
        if self.source.graph_id < self.destination.graph_id:
            return hash((hash(self.source), hash(self.destination)))
        return hash((hash(self.destination), hash(self.source)))

    def delete(self):
        """
        Remove this :py:class:`Edge` from the :py:class:`ExperimentGraph`.
        This sets the :py:attr:`Edge.valid` property to ``False``.
        """
        self.source.g.g.remove_edge(self.source.graph_id, self.destination.graph_id)
        self.valid = False

    def __iter__(self):
        """
        Iterate over the :py:class:`Edge`.

        Returns:
            An iterator that iterates over the :py:class:`Edge` properties.
        """
        return iter(
            self.source.g.g.adj[self.source.graph_id][self.destination.graph_id]
        )


class VertexIterator:
    """
    A custom :py:class:`Vertex` iterator which parses the graph and returns
    the next :py:class:`Vertex`.
    """

    def __init__(self, graph, vertex_iterable):
        """
        Set up the :py:class:`Vertex` iterator.

        Args:
            graph (ExperimentGraph): The experiment graph to iterate over.
            vertex_iterable: An iterable that provides :py:class:`Vertex` instances.

        Attributes:
            g (ExperimentGraph): The experiment graph to iterate over.
            vertex_iter (iterator): The iterator over the :py:class:`Vertex`
                instances.
        """
        self.g = graph  # pylint: disable=invalid-name
        self.vertex_iter = iter(vertex_iterable)

    def __iter__(self):
        """
        Return this :py:class:`VertexIterator`.

        Returns:
            VertexIterator: Returns this :py:class:`VertexIterator`.
        """
        return self

    def __next__(self):
        """
        Get the next :py:class:`Vertex` in the graph.

        Returns:
            Vertex: The next :py:class:`Vertex` in the graph.

        Raises:
            NoSuchVertexError: If the :py:class:`Vertex` ID was not found in the graph.
        """
        try:
            return self.g.g.nodes[next(self.vertex_iter)]["object"]
        except KeyError as exp:
            raise NoSuchVertexError(
                f"Vertex ID {exp!s} not found in given graph."
            ) from exp


class EdgeIterator:
    """
    A custom :py:class:`Edge` iterator which parses the graph and returns the
    next :py:class:`Edge`.
    """

    def __init__(self, graph, source_id_list):
        """
        Set up the :py:class:`Edge` iterator.

        Args:
            graph (ExperimentGraph): The experiment graph to iterate over.
            source_id_list (list): A list of :py:class:`Vertex` IDs that are the
                source of an :py:class:`Edge`.

        Raises:
            NoSuchVertexError: If the :py:class:`Vertex` ID was not found in the graph.
        """
        self.g = graph  # pylint: disable=invalid-name
        self.source_ids = []

        self.seen_edge_objects = set()
        self.total_edges = nx.number_of_edges(self.g.g)

        temp_sid_list = list(source_id_list)
        sid_set = set()
        for sid in temp_sid_list:
            # Don't accept duplicate IDs.
            if sid in sid_set:
                continue

            sid_set.add(sid)
            self.source_ids.append(sid)

            # Make sure every ID is actually in the given graph.
            if sid not in self.g.g:
                raise NoSuchVertexError(
                    f"(Source) Vertex ID {sid!s} not found in given graph."
                )

        self.current_adj_source = None
        self.current_source = None

        self.e_iter = self.g.g.edges(self.source_ids).__iter__()

    def __iter__(self):
        """
        Return this :py:class:`EdgeIterator`.

        Returns:
            EdgeIterator: Returns this :py:class:`EdgeIterator`.
        """
        return self

    def __next__(self):
        """
        Get the next :py:class:`Edge` in the graph.

        Returns:
            Edge: The next :py:class:`Edge` in the graph.

        Raises:
            Exception: If the :py:class:`Edge` object could not be found. This is most likely
                caused because the graph has not been constructed with the correct APIs.
                Users can double check that all additions/deletions are going though
                the graph API.
        """
        next_edge = next(self.e_iter)
        # This should never raise a KeyError if the graph has been constructed
        # through the correct APIs.
        try:
            return self.g.g[next_edge[0]][next_edge[1]]["object"]
        except KeyError as exc:
            raise Exception(
                "The edge object could not be found"
                " this is most likely because the graph has"
                " not been constructed with the correct APIs."
                " double check that all additions/deletions are"
                " going though the graph API."
            ) from exc


class ExperimentGraph:
    """
    The graph describing a FIREWHEEL experiment.

    This is a FIREWHEEL specific graph that leverages :py:mod:`networkx` but makes some
    modifications to all :py:class:`Vertex` instances/:py:class:`Edges <Edge>` as they
    are added to the graph.

    It conducts some specific error checking and also provides methods for
    getting :py:class:`Vertices <Vertex>` by different properties (i.e. name and ID) as well
    as an efficient method for getting the all-pairs shortest path for a graph.
    """

    def __init__(self):
        """
        Initialize the :py:class:`networkx.Graph`, set up a counter and the logger.

        Attributes:
            g (networkx.Graph): The NetworkX graph that underlies this FIREWHEEL graph.
            last_node_id (int): The ID of the last node in the graph.
        """
        self.g = nx.Graph()  # pylint: disable=invalid-name
        self._setup_logging()
        self.last_node_id = 0

    def _setup_logging(self):
        """
        Set up the logger for the experiment graph class.
        """
        self.log = Log(name="ExperimentGraph").log

    def __getstate__(self):
        state = self.__dict__.copy()
        del state["log"]
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._setup_logging()

    def _add_vertex(self, new_id=None):
        """
        Add a :py:class:`Vertex` object to the graph.

        Args:
            new_id (int): A possible ID for the new node. If :py:obj:`None`,
                then one will be created.

        Returns:
            int: The ID of the new :py:class:`Vertex`.

        Raises:
            RuntimeError: If there is a conflict with the provided :py:class:`Vertex` ID and
                an existing :py:class:`Vertex` in the graph.
        """
        if new_id is None:
            new_id = self.last_node_id + 1
            if new_id in self.g:
                # The new_id conflicts with an existing one.
                # so we get all ID's, sort them, and increment the last one.
                ids = list(self.g.nodes)
                ids.sort()
                new_id = ids[-1] + 1

        if new_id in self.g:
            raise RuntimeError(f"The node ID {new_id} conflicts with an existing node!")

        self.g.add_node(new_id)
        if isinstance(new_id, int):
            self.last_node_id = new_id
        return new_id

    def _add_edge(self, source_id, dest_id):
        """
        Add an :py:class:`Edge` object to the graph.

        Args:
            source_id (int): The source :py:class:`Vertex`'s ID.
            dest_id (int): The destination :py:class:`Vertex`'s ID.

        Raises:
            NoSuchVertexError: If either the source or destination :py:class:`Vertex`
                cannot be found.
        """
        if source_id not in self.g:
            raise NoSuchVertexError(source_id)
        if dest_id not in self.g:
            raise NoSuchVertexError(dest_id)
        self.g.add_edge(source_id, dest_id)

    def get_vertices(self):
        """
        Get an iterator of the graph :py:class:`Vertex` instances.

        Returns:
            VertexIterator: The :py:class:`Vertex` iterator for the experiment graph.
        """
        return VertexIterator(self, self.g)

    def get_edges(self):
        """
        Get an iterator of the graph :py:class:`Edges <Edge>`.

        Returns:
            EdgeIterator: The :py:class:`EdgeIterator` for the experiment graph.
        """
        return EdgeIterator(self, self.g)

    def find_edge(self, ep1, ep2):
        """
        Try to find an :py:class:`Edge` based on the passed in :py:class:`Vertex` instances.

        Note:
            This is a :py:mod:`networkx` specific method for finding the :py:class:`Edge`.

        Args:
            ep1 (Vertex): The first of the :py:class:`Vertices <Vertex>` that is part of
                the :py:class:`Edge` being found.
            ep2 (Vertex): The second of the :py:class:`Vertices <Vertex>` that is part of
                the :py:class:`Edge` being found.

        Returns:
            Edge: The found :py:class:`Edge`, or None if an error has occurred.
        """
        try:
            edge = self.g.edges[ep1.graph_id, ep2.graph_id]["object"]
            return edge
        except (KeyError, AttributeError) as exp:
            self.log.error("Unable to find edge: %s->%s", ep1, ep2)
            self.log.exception(exp)

        return None

    def find_vertex_by_id(self, vert_id):
        """
        Try to find a :py:class:`Vertex` based on the passed in :py:class:`Vertex` ID.

        Note:
            This is a :py:mod:`networkx` specific method for finding the :py:class:`Vertex`.

        Args:
            vert_id (int): The ID of the :py:class:`Vertex` we are trying to locate.

        Returns:
            Vertex: The found :py:class:`Vertex`, or :py:data:`None` if the :py:class:`Vertex`
            cannot be found.
        """
        try:
            vertex = self.g.nodes[vert_id]["object"]
            return vertex
        except (KeyError, AttributeError) as exp:
            self.log.error("Unable to find vertex: %s", vert_id)
            self.log.exception(exp)

        return None

    def find_vertex(self, name):
        """
        Try to find a :py:class:`Vertex` based on the passed in :py:class:`Vertex` name.

        Note:
            This is a :py:mod:`networkx` specific method for finding the :py:class:`Vertex`.


        Args:
            name (str): The name of the :py:class:`Vertex` we are trying to locate.

        Returns:
            Vertex: The found :py:class:`Vertex`, or None if the :py:class:`Vertex`
            cannot be found.
        """
        for vertex in self.get_vertices():
            try:
                if vertex.name == name:
                    return vertex
            except AttributeError:
                continue
        return None

    def _single_process_all_pairs_shortest_path(self, vertex_filter, path_action):
        """
        All pairs shortest path with a single thread of execution. Computes
        shortest path among all pairs where each :py:class:`Vertex` matches vertex_filter,
        and calls path_action with the path between each pair.

        Args:
            vertex_filter (func): Callable taking a vertex (object) and returning
                :py:data:`True` or :py:data`False`.
            path_action (func): Callable ``path_action(path_source, path_dest, current_path)``
                Where ``path_source`` is a :py:class:`Vertex`,
                ``path_dest`` is a :py:class:`Vertex`,
                and ``current_path`` is a list of :py:class:`Vertex` on the path.
                The return value for ``path_action`` is ignored.
        """
        vert_it = filter(vertex_filter, VertexIterator(self, self.g))
        for source in vert_it:
            paths = nx.single_source_shortest_path(self.g, source.graph_id)
            for dest, dest_list in paths.items():
                dest_obj = self.g.nodes[dest]["object"]
                if vertex_filter(dest_obj) is True:
                    cur_path = []
                    for vert in dest_list:
                        cur_path.append(self.g.nodes[vert]["object"])
                    path_action(source, dest_obj, cur_path)

    def filtered_all_pairs_shortest_path(
        self, vertex_filter=None, path_action=None, num_workers=0, sample_pct=0
    ):
        """
        All pairs shortest path with multiple threads of execution. Computes
        shortest path among all pairs where each :py:class:`Vertex` matches vertex_filter,
        and calls path_action with the path between each pair.

        Args:
            vertex_filter (func): Callable taking a :py:class:`Vertex` and returning
               :py:data:`True` or :py:data:`False`.
            path_action (func): Callable ``path_action(path_source, path_dest, current_path)``
                Where ``path_source`` is a :py:class:`Vertex`, ``path_dest`` is a
                :py:class:`Vertex`, and ``current_path`` is a list of :py:class:`Vertex`
                on the path. The return value for ``path_action`` is ignored.
            num_workers (int): Number of threads which will calculate the all-pairs shortest path.
            sample_pct (int): The percentage of nodes for which the all pairs will be preformed.
                This speeds up the time it takes for the calculation to occur.

        Returns:
            None: If there are no other workers, the method
            :py:meth:`_single_process_all_pairs_shortest_path` is returned.
        """
        if num_workers == 0:
            return self._single_process_all_pairs_shortest_path(
                vertex_filter, path_action
            )

        def do_source(graph, vertex_filter, source_queue, path_queue):
            for source_id in iter(source_queue.get, "STOP"):
                paths = nx.single_source_shortest_path(graph, source_id)
                for dest, value in paths.items():
                    dest_obj = self.g.nodes[dest]["object"]
                    if vertex_filter(dest_obj) is True:
                        path_queue.put((source_id, dest, value))
            path_queue.put("STOP")

        vert_it = filter(vertex_filter, VertexIterator(self, self.g))
        workers = []
        source_queue = Queue()
        path_queue = Queue()

        self.log.debug("Initializing %d worker processes.", num_workers)
        for _ in range(num_workers):
            proc = Process(
                target=do_source, args=(self.g, vertex_filter, source_queue, path_queue)
            )
            proc.start()
            workers.append(proc)

        self.log.debug("Handing out sources.")
        if sample_pct:
            self.log.debug("Only sampling %s of sources.", sample_pct)
        for source in vert_it:
            if sample_pct:
                if random.random() < sample_pct:
                    source_queue.put(source.graph_id)
            else:
                source_queue.put(source.graph_id)

        for _ in range(num_workers):
            source_queue.put("STOP")

        self.log.debug("Processing resulting paths.")
        ends = 0
        while ends < num_workers:
            result = path_queue.get(block=True)
            if result == "STOP":
                ends += 1
                continue

            # Get the objects.
            source_obj = self.g.nodes[result[0]]["object"]
            dest_obj = self.g.nodes[result[1]]["object"]
            path_objs = []
            for vert in result[2]:
                path_objs.append(self.g.nodes[vert]["object"])

            # Do the path action.
            path_action(source_obj, dest_obj, path_objs)

        self.log.debug("Waiting for workers to terminate.")
        for worker in workers:
            worker.join()
        return None
