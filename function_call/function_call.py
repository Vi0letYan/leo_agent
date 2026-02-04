# 导入异步OpenAI库
from openai import AsyncOpenAI
import os
# 导入异步库，用于异步任务，不用等待返回结果
import asyncio
# 导入json库
import json

# 导入百度搜索库，用于搜索百度，其中一个 function tool
from baidusearch.baidusearch import search
# 导入时间库，用于获取当前时间，其中一个 function tool
from datetime import datetime


'''
初始化OpenAI API，作为client，用于与 LLM 进行交互
api_key: 阿里云的 API 密钥
base_url: 阿里云的 API 地址
'''
client = AsyncOpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")


'''
定义 function tool 函数
'''

'''
查询百度搜索工具
async def 定义异步函数，用于异步任务，不用等待返回结果，需要 import asyncio
query: 搜索关键词
num_results: 搜索结果数量，默认3条
return: 搜索结果

规范格式：
(query: str, num_results: int = 3) -> str 明确函数的输入、输出类型
'''
async def baidu_search(query: str, num_results: int = 3) -> str:
    baidu_results = search(query, num_results=num_results)
    # 转换为json
    baidu_results = json.dumps(baidu_results, ensure_ascii=False)
    return baidu_results

# 查询当前时间的工具
async def get_current_time() -> str:
    current_time = datetime.now()
    formatted_time = current_time.strftime('%Y-%m-%d %H:%M:%S')
    return formatted_time


'''
定义 function schema
让 LLM 知道有哪些 function tool 可以调用
function tool 的名称、描述、输入参数。如果没有输入参数，则不需要 parameters 字段

function schema 的格式：
{
    "type": "function",
    "function": {
        "name": "function_name",
        "description": "function_description",
        "parameters": {
            "type": "object",
            "properties": {
                "parameter_name": {
                    "type": "parameter_name_type",
                    "description": "parameter_description",
                }
            },
            "required": ["parameter_name"]
        }
    }
}]

tools 会被拼接成 prompt 的一部分传递给 LLM，但是拼接方式并不公开
'''

tools = [{
    "type": "function",
    "function":{
        "name": "baidu_search",
        "description": "对于用户提出的问题，如果需要使用搜索引擎查询，请使用此工具。",
        "parameters":{
            "type": "object",
            "properties":{
                "query":{
                    "type": "string",
                    "description": "搜索关键词"
                },
                "num_results":{
                    "type": "integer",
                    "description": "搜索结果数量",
                    "default": 3
                }
            },
            "required": ["query"]
        }
    }
},{
    "type": "function",
    "function":{
        "name": "get_current_time",
        "description": "需要查询时间时使用此工具。"
    }
}]


'''
定义 function call 函数

function call 函数的作用：
1. 根据用户问题，选择合适的 function tool
2. 根据选择的 function tool，生成合适的输入参数
3. 调用 function tool，获取结果
4. 将结果返回给用户

Args:
    query (str): 用户输入的query
    tools (list): function schema 列表

Returns:
    function_name (str): function tool 的名称
    function_arguments (str): function tool 的输入参数
    fun_id (str): function tool 的 ID，每次工具调用都会有一个编号 id，同一个工具在一次与 LLM 调用多次，id 会不同
    prompt (list): 传递给 LLM 用于交互的 prompt，包括 system content、user content、assistant content、tool content
    completions_content (str): LLM 的最终回答内容
'''

async def single_function_request(query: str, tools: list) -> tuple[str, str, str, list, str]:
    # 初始化 prompt
    prompt = []
    # 添加 system content
    prompt.append({
        "role": "system",
        "content": "你是一个AI助手，请根据用户的问题给出回答，可以采用工具调用帮助回答问题"
    })
    # 添加 user content，这是用户的输入
    prompt.append({
        "role": "user",
        "content": query
    })

    '''
    将 prompt 传递给 LLM，可以是使用自己本地的 LLM，这里是调用的 api 接口
    await 用于等待异步任务完成，因为使用了异步 AsyncOpenAI 作为 client

    model: 使用的大模型
    messages: 传递给 LLM 用于交互的 prompt
    tools: function schema 列表
    tool_choice: 工具选择模式，包括 "auto", "required", "none"
    stream: 是否流式输出，流式输出可以边接收边处理，非流式输出需要等待全部接收完再处理
    '''
    completions = await client.chat.completions.create(model="qwen-turbo",
                                                        messages=prompt,
                                                        tools=tools,
                                                        tool_choice="auto",
                                                        stream=True)

    # 初始化 function_name、function_arguments、fun_id
    function_name = ""
    function_arguments = ""
    completions_content = ""
    first_chunk = True
    fun_id = None

    # 处理流式输出
    '''
    ┌─────────────────────────────────────────────────┐
    │          async for chunk in response            │
    │              (逐块接收响应)                       │
    └────────────────────┬────────────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  chunk 有 tool_calls? │
            └───────────┬───────────┘
                        │
            ┌──────────┴──────────┐
            │                     │
            YES                   NO
            │                     │
            ▼                     ▼
    ┌──────────────┐    ┌───────────────────┐
    │  是第一个块?  │    │ 有 content 内容?  │
    └──────┬───────┘    └─────────┬─────────┘
            │                      │
        ┌─────┴─────┐               YES
        │           │                │
    YES         NO                ▼
        │           │         ┌─────────────────┐
        ▼           ▼         │ 累积并打印文本   │
    ┌────────┐ ┌────────┐     │ completions_content│
    │提取:    │ │继续累积 │     └─────────────────┘
    │- name  │ │arguments│
    │- id    │ └────────┘
    │- args  │
    └────────┘

    如果chunk 有 tool_calls的话，就会只有function call相关信息，不会有正常的回答内容
    如果chunk 没有 tool_calls的话，就会有正常的回答内容
    这两部分是互斥的
    情况	        tool_calls	content
    LLM 决定调用工具  ✅ 有数据	 ❌ 为空/None
    LLM 直接回答	❌ 为空/None ✅ 有数据
    '''
    
    async for chunk in completions:
        if chunk.choices[0].delta.tool_calls:
            if first_chunk:  # 单 function tool 调用，所以只提取 choices[0]
                function_name = chunk.choices[0].delta.tool_calls[
                    0].function.name
                function_arguments += chunk.choices[0].delta.tool_calls[
                    0].function.arguments
                fun_id = chunk.choices[0].delta.tool_calls[0].id
                first_chunk = False
            else:
                if chunk.choices[0].delta.tool_calls[0].function.arguments:
                    function_arguments += chunk.choices[0].delta.tool_calls[
                        0].function.arguments
            # completions_content += chunk.choices[0].delta.content
            # print(f"completions_content: {completions_content}")
        else:
            # 不是函数调用，正常回答
            if chunk.choices[0].delta.content:
                completions_content += chunk.choices[0].delta.content

    return function_name, function_arguments, fun_id, prompt, completions_content


'''
定义 字符串 -> function tool 的映射
LLM 返回的 function name 是字符串，需要根据字符串找到对应的 function tool
'''
tool_mapping = {
    "baidu_search": baidu_search,
    "get_current_time": get_current_time,
}

'''
定义 assistant content 模板
assistant content 是 LLM 的回答内容，需要根据 function tool 的返回结果更新 assistant content
'''
assistant_content_template = {
    "content": "",
    "refusal": None,
    "role": "assistant",
    "audio": None,
    "function_call": None,
    "tool_calls": [{
        "id": "call_xxx",
        "function": {
            "arguments": "",
            "name": "",
        },
        "type": "function",
        "index": 0,
    }],
}


'''
串联完整的 function call 过程
'''
async def function_call_process(query: str, tools: list) -> str:
    # 1. 根据用户问题，选择合适的 function tool
    # 这里与 LLM 进行了第一次交互
    function_name, function_arguments, fun_id, prompt, completions_content = await single_function_request(query, tools)

    if function_name:
        print(
            f"执行函数调用：工具名称：{function_name}，工具参数：{function_arguments}，工具调用id：{fun_id}"
        )

        # 2. 根据选择的 function tool，生成合适的输入参数
        function = tool_mapping[function_name]
        print(f"选择的 function tool：{function}")

        # 3. 解析函数入参（将字符串转换为字典）
        # "{'arg1': xxxx}" -> {'arg1': xxxx}
        function_arguments_dict = json.loads(function_arguments)
        print(f"函数入参：{function_arguments_dict}")

        # 4. 执行函数
        function_result = await function(**function_arguments_dict)

        # 5. 打印函数结果
        print(f"函数执行结果：{function_result}")

        # 6.1 assistant content 中添加 function call 信息再返回给 LLM
        # 让 LLM 知道你执行了什么函数，执行结果是什么。让 LLM 根据 function call 信息和执行结果生成最终的回答。
        assistant_content = assistant_content_template.copy()
        # 更新了 assistant_content_template 中的 tool_calls 信息
        assistant_content["tool_calls"][0]["id"] = fun_id
        assistant_content["tool_calls"][0]["function"].update({
            'arguments': function_arguments,
            'name': function_name
        })

        # 6.2 将 assistant content 添加到 prompt 中
        prompt.append(assistant_content)

        # 6.3 将 tool 输出信息添加到 prompt 中
        prompt.append({
            "role": "tool",
            "content": function_result,
            "tool_call_id": fun_id
        })

        print("prompt: ", prompt)

        # 7. 将 prompt 传递给 LLM
        # 这里与 LLM 进行了第二次交互
        # LLM 获得了 function call 信息和执行结果，生成最终的回答。
        completions = await client.chat.completions.create(model="qwen-turbo",
                                                            messages=prompt,
                                                            tools=tools,
                                                            tool_choice="auto",
                                                            stream=True)
        
        # 处理流式输出
        async for chunk in completions:
            if chunk.choices[0].delta.content:
                completions_content += chunk.choices[0].delta.content
                print(chunk.choices[0].delta.content, end="", flush=True)
    else:
        completions_content = completions_content
        print(f"没有执行函数调用，直接返回回答：{completions_content}")

if __name__ == "__main__":
    # query = "请你确认一下现在的时间"
    query = "黑神话悟空是什么时候发售的"
    tools = tools
    asyncio.run(function_call_process(query, tools))