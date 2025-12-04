from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def param_replace(context, **kwargs):
    """
    Hàm này giúp thay thế hoặc thêm tham số vào URL hiện tại.
    Ví dụ: Đang ở ?page=1&q=abc -> Muốn đổi sort thì giữ nguyên q=abc
    """
    d = context['request'].GET.copy()
    for k, v in kwargs.items():
        d[k] = v
    return d.urlencode()
