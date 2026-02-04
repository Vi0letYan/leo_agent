# 申请阿里云的 LLM api

1. 使用支付宝登录 https://bailian.console.aliyun.com/cn-beijing/?tab=home#/home
2. 完成实名认证后会有新人免费 token 领取，点击领取
3. 领取完毕后即可任意使用模型广场内的 LLM
4. 在 https://bailian.console.aliyun.com/cn-beijing/?tab=model#/api-key 中创建自己的 api-key，这就是你的账号，这个 api-key 可以使用所有免费 token 可用的 LLM
5. 在终端中输入 export DASHSCOPE_API_KEY="your api-key"。此时就已经可以在这个终端中运行运行使用 api 调用的 LLM 了

# 环境配置

创建 conda 环境
    conda create -n leo-agent python=3.13 -y
    conda activate leo-agent

安装依赖
    ./env_setup.sh


# utils

tools list[dict]：会被拼接成 prompt 的一部分传递给 LLM，让 LLM 知道哪些 function tool 可以被调用、调用需要的输入参数是什么

tools_mapping dict：定义 字符串 -> function tool 的映射。LLM 返回的 function name 是字符串，需要根据字符串找到对应的 function tool

assistant_content_template dict：assistant content 是 LLM 的回答内容，需要根据 function tool 的返回结果更新 assistant content

# function call 流程

组织第一次 (prompt：system, user) -> 第一次与 LLM 进行交互：与 tools list[dict] 一起传递给 LLM -> 处理第一次 LLM 返回的内容，分类讨论（当需要 function call（chunk.choices[0].delta.tool_calls 不为 none） 时，统计 function call 需要的信息，这时不会有直接的回复，强制输出 completions_content += chunk.choices[0].delta.content 是空的；如果没有 function call 需求，则累计输出作为 LLM 的直接回复） -> 通过 function call 的信息传入函数中进行得到函数结果（这里与 LLM 无关） -> 组织第二次 (prompt：system, user, assistant, tool) -> 第二次与 LLM 进行交互：与 tools list[dict] 一起传递给 LLM -> 直接累计输出，这是 LLM 的回答是携带着 function tool 的内容的完整输出