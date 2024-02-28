from simple_copoco import Register, clarify_register_sections, register_as, create_subclasses_dict
import pytest


class SomeKlass:
    ...


@register_as('dummy', passes_on_children=True)
class DummyKlass(SomeKlass):
    ...


class DummyKlassTheSecond(DummyKlass):
    ...


@register_as('other')
class DummyKlassTheThird(DummyKlass):
    ...


@register_as('not_registered')
class NotRegisteredKlass(SomeKlass):
    ...


class TestRegister:
    def test_construction_without_package(self):
        new_register = Register(DummyKlass)

        assert "DummyKlassTheSecond" in new_register.dummy.keys()
        assert "DummyKlassTheThird" in new_register.other.keys()
        assert not hasattr(new_register, "not_registered")

    def test_construction_with_package(self):
        from . import helper_pkg_for_test
        from .helper_pkg_for_test.level1 import BaseKlass
        new_register = Register(BaseKlass, package=helper_pkg_for_test, include_parent=False)

        assert set(new_register.register['kind1'].keys()) == {'Klass1Level2', 'Klass1Level3', 'Klass2Level1',
                                                              'Klass1Level4'}
        assert set(new_register.register.keys()) == {'kind1', 'kind2', 'built_ins'}
        assert set(new_register.register['built_ins'].keys()) == {'Klass1Level1'}
        assert set(new_register.register['kind2'].keys()) == {'Klass2Level2'}

    @pytest.mark.filterwarnings("ignore:.*name conflicts.*")
    def test_update(self):
        register = Register(DummyKlass)

        DummyKlassTheSecond.register_section = "dummy_bummy"
        DummyKlassTheSecond.__name__ = "NewDummyKlassTheSecond"
        register.update_register()

        assert "NewDummyKlassTheSecond" in register.dummy_bummy.keys()

    def test_extend(self):
        register = Register(DummyKlass)

        register.extend(NotRegisteredKlass)
        assert "NotRegisteredKlass" in register.not_registered.keys()

        class JustKlass:
            ...

        with pytest.raises(AttributeError):
            register.extend(JustKlass)

    def test_cascade_inheritance(self):
        @register_as('simple', passes_on_children=True)
        class SimpleKlass:
            ...

            def __init__(self):
                ...

        class MoreSimpleKlass(SimpleKlass):
            def __init__(self):
                super(MoreSimpleKlass, self).__init__()

        class TheSimplestKlass(MoreSimpleKlass):
            def __init__(self):
                super(TheSimplestKlass, self).__init__()

        class NoLongerSimpleButDumb(TheSimplestKlass):
            def __init__(self):
                super(NoLongerSimpleButDumb, self).__init__()

        register = Register(include_parent=False)
        assert "SimpleKlass" in register.simple.keys()
        assert "NoLongerSimpleButDumb" in register.simple.keys()

    def test_stopped_cascade_inheritance(self):
        class TheSimplestKlass:
            ...

        @register_as('simple', passes_on_children=False)
        class SimpleKlass(TheSimplestKlass):
            ...

            def __init__(self):
                ...

        class MoreSimpleKlass(SimpleKlass):
            def __init__(self):
                super(MoreSimpleKlass, self).__init__()

        register = Register()

        assert "MoreSimpleKlass" not in register.simple.keys()
        assert "SimpleKlass" in register.simple.keys()


def test_clarify_register_sections():

    with pytest.raises(TypeError):
        clarify_register_sections({})

    @register_as('simple', passes_on_children=True)
    class ThisKlass:
        ...

    class NoKlass(ThisKlass):
        ...

    @register_as('hard', passes_on_children=False)
    class PlentyOfKlass(NoKlass):
        ...

    class OnlySwag(PlentyOfKlass):
        ...

    subs = clarify_register_sections(
        create_subclasses_dict(ThisKlass, include_parent=True)
    )

    assert 'NoKlass' in subs['simple'].keys()
    assert 'PlentyOfKlass' in subs['hard'].keys()
    assert 'PlentyOfKlass' not in subs['simple'].keys()
    assert 'OnlySwag' not in subs['hard'].keys()
    assert 'OnlySwag' not in subs['simple'].keys()


def test_create_subclasses_dict():

    @register_as('simple', passes_on_children=True)
    class ThisKlass:
        ...

    class NoKlass(ThisKlass):
        ...

    @register_as('hard', passes_on_children=True)
    class PlentyOfKlass(NoKlass):
        ...

    subs = create_subclasses_dict(ThisKlass, include_parent=True)

    assert len(subs) == 3
