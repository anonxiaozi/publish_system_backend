# -*- coding: utf-8 -*-
# @Time: 2020/4/17
# @File: urls

from django.urls import path
from .views import TemplateView, DistributeView, GuiderView, pull_view, GetDistHistory, ModifyStatus, MonitorView, AccountUrls

app_name = 'publish'

urlpatterns = [
    path('', TemplateView.as_view(), name='list'),
    path('distribute', DistributeView.as_view(), name='dist'),
    path('update_cr/<str:cr_name>', DistributeView.as_view(), name='batch_dist'),
    path('guider', GuiderView.as_view(), name='guider'),
    path('pull', pull_view, name='pull'),
    path('record', GetDistHistory.as_view(), name='record'),
    path('status/<str:cr>/<int:status>', ModifyStatus.as_view(), name='online'),
    path('monitor', MonitorView.as_view(), name="monitor"),
    path('accounts', AccountUrls.as_view(), name='get_accounts'),
    path('account/<str:account>', AccountUrls.as_view(), name='get_single_account'),
    path('update_record', AccountUrls.as_view(), name='batch_update_record'),
]
