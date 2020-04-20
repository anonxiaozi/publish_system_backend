# 落地页发布系统后端

* **TemplateView** 视图：列出所有模板
* **ModifyStatus** 视图：更改模板的在线下线状态，下线的模板不能发布
* **DistributeView** 视图：通过制定的模板发布页面到web服务器
* **GuiderView** 视图：所有已发布网站的客服信息
* **pull_view** 视图：手动从git服务器拉取模板，默认是在模板更新后，由git服务器配置的webhook触发
* **GetDistHistory** 视图：发布记录
* **AccountUrls** 视图：通过账户概念，批量修改已发布网站的客服信息
* **MonitorView** 视图：监控指定的网站，通过requests请求，将失败结果发送到钉钉

---
