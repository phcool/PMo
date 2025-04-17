#!/bin/bash
# 手动获取论文的bash脚本

# 设置默认值
API_URL="http://localhost:8000/api/scheduler/fetch"
MAX_RESULTS=50
CATEGORIES=null  # null表示使用默认类别

# 解析命令行参数
while [[ $# -gt 0 ]]; do
  case $1 in
    --max-results|-m)
      MAX_RESULTS="$2"
      shift 2
      ;;
    --categories|-c)
      shift
      # 收集所有类别参数
      CATEGORIES="["
      while [[ $# -gt 0 && ! $1 =~ ^- ]]; do
        CATEGORIES="${CATEGORIES}\"$1\","
        shift
      done
      # 删除最后一个逗号，添加右括号
      if [[ $CATEGORIES != "[" ]]; then
        CATEGORIES="${CATEGORIES%,}]"
      else
        CATEGORIES="null"  # 没有提供类别
      fi
      ;;
    --url|-u)
      API_URL="$2"
      shift 2
      ;;
    --help|-h)
      echo "用法: $0 [选项]"
      echo "选项:"
      echo "  --max-results, -m <数字>   最大获取论文数量，默认50"
      echo "  --categories, -c <类别...>  要获取的论文类别，例如: cs.LG cs.AI cs.CV"
      echo "  --url, -u <URL>            API URL，默认 http://localhost:8000/api/scheduler/fetch"
      echo "  --help, -h                 显示此帮助信息"
      exit 0
      ;;
    *)
      echo "未知选项: $1"
      echo "使用 --help 查看帮助"
      exit 1
      ;;
  esac
done

# 构造请求体
REQUEST_BODY="{\"max_results\": $MAX_RESULTS"
if [[ $CATEGORIES != "null" ]]; then
  REQUEST_BODY="$REQUEST_BODY, \"categories\": $CATEGORIES"
fi
REQUEST_BODY="$REQUEST_BODY}"

echo "开始手动获取论文..."
echo "API URL: $API_URL"
echo "请求内容: $REQUEST_BODY"
echo "正在获取中，请稍候..."

# 发送请求
response=$(curl -s -X POST -H "Content-Type: application/json" -d "$REQUEST_BODY" "$API_URL")

# 检查curl是否成功
if [ $? -ne 0 ]; then
  echo "❌ 请求失败，请检查API服务是否运行或网络连接是否正常"
  exit 1
fi

# 解析返回结果
status=$(echo $response | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
message=$(echo $response | grep -o '"message":"[^"]*"' | cut -d'"' -f4)
count=$(echo $response | grep -o '"count":[0-9]*' | cut -d':' -f2)

if [[ "$status" == "success" ]]; then
  echo "✅ 获取成功!"
  echo "获取了 $count 篇新论文"
  if [[ -n "$message" ]]; then
    echo "详细信息: $message"
  fi
else
  echo "❌ 获取失败!"
  echo "错误信息: $message"
  exit 1
fi 