from django import template

register = template.Library()

@register.filter(name='has_group')
def has_group(user, group_name):
    """Kiểm tra xem user có thuộc nhóm group_name không"""
    return user.groups.filter(name=group_name).exists()