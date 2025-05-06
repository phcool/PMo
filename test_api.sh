#!/bin/bash

# 设置API基础URL
API_BASE="http://localhost:8000"

# 测试函数
test_endpoint() {
    local method=$1
    local endpoint=$2
    local data=$3
    
    echo "测试 $method $endpoint"
    
    if [ "$method" == "GET" ]; then
        curl -s -X GET "$API_BASE$endpoint" -H "Content-Type: application/json" | jq '.' || echo "请求失败"
    elif [ "$method" == "POST" ]; then
        if [ -z "$data" ]; then
            curl -s -X POST "$API_BASE$endpoint" -H "Content-Type: application/json" | jq '.' || echo "请求失败"
        else
            curl -s -X POST "$API_BASE$endpoint" -H "Content-Type: application/json" -d "$data" | jq '.' || echo "请求失败"
        fi
    fi
    
    echo "----------------------------------------"
}

# 测试主页
echo "测试前端主页"
curl -s "$API_BASE/" | grep -q "DL Paper Monitor" && echo "前端主页加载成功" || echo "前端主页加载失败"
echo "----------------------------------------"

# 测试API端点
test_endpoint "GET" "/api/papers?limit=5&offset=0"
test_endpoint "GET" "/api/papers/count"
test_endpoint "POST" "/api/search" '{"query": "machine learning", "limit": 5}'
test_endpoint "GET" "/api/user/preferences"

# 测试静态资源
echo "测试静态资源"
curl -I "$API_BASE/assets/index-BBqwikV8.css" | grep -q "200 OK" && echo "CSS资源加载成功" || echo "CSS资源加载失败"
curl -I "$API_BASE/assets/index-CM2L4uqk.js" | grep -q "200 OK" && echo "JS资源加载成功" || echo "JS资源加载失败"
echo "----------------------------------------" 