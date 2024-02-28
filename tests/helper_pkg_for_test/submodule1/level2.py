from simple_copoco import register_as
from ..level1 import BaseKlass, Klass1Level1


@register_as('kind1', passes_on_children=True)
class Klass1Level2(BaseKlass):
    ...


@register_as('kind2')
class Klass2Level2(Klass1Level1):
    ...
