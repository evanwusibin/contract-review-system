# 切片Spec · 函数级

本目录包含合同评审系统 Slice 1-7 的函数级执行Spec。每个切片Spec定义了具体函数的输入、输出、异常处理和验收测试。

## 切片索引

| 文件 | 切片 | 状态 |
|---|---|---|
| `切片1_PDF导入与任务幂等.md` | S1 | accepted（测试在 test_import_contract.py） |
| `切片2_质量诊断与阻塞.md` | S2 | accepted |
| `切片3_解析字段与证据定位.md` | S3 | accepted（Mock OCR） |
| `切片4_规则命中与风险联动.md` | S4 | accepted |
| `切片5_建议结果与会签.md` | S5 | accepted |
| `切片6_版本保存与历史恢复.md` | S6 | accepted |
| `切片7_调用端演示闭环与mock回写.md` | S7 | accepted（pytest 验证） |
| `切片7_MinIO存储与完整性.md` | S7-依赖 | blocked（Docker 不可用） |