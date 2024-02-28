from simple_copoco.objects_register import register_as


class BaseKlass:
    ...


class Klass1Level1(BaseKlass):
    ...


@register_as('kind1')
class Klass2Level1(BaseKlass):
    ...
