import logging
import asyncio
import subprocess
import time
import os, signal
from typing import Optional, Any
import openai
import copy


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

OPENAI_COMPLETION_KWS = ["gpt-3.5-turbo-instruct", "davinci-00", "babbage-00"]

# # Script to test the server
# import openai
# import time

# client = openai.OpenAI(api_key="token-abc123", base_url="http://localhost:8000/v1")
# messages = [{"role": "user", "content": "count from 1 to 100, for example, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10..."}]
# model = "meta-llama/Meta-Llama-3-8B-Instruct"
# max_tokens = 512
# stop = None
# extra_body = {}
# kwargs = {}

# first_token = True
# content = ""
# stream = client.chat.completions.create(
#     model=model,
#     messages=messages,
#     stream=True,
#     stream_options={"include_usage": True},
#     max_tokens=max_tokens,
#     stop=stop,
#     extra_body=extra_body,
#     **kwargs,
# )
# time0 = time.time()
# for chunk in stream:
#     if first_token:
#         TTFT = time.time() - time0
#         first_token = False
#     if chunk.usage:
#         prompt_tokens = chunk.usage.prompt_tokens
#         completion_tokens = chunk.usage.completion_tokens
#         total_tokens = chunk.usage.total_tokens
#         Latency = time.time() - time0
#     content += chunk.choices[0].delta.content or ""

# TPOT = (Latency - TTFT) / completion_tokens
# TPS = completion_tokens / Latency

# print("TTFT: ", TTFT)
# print("Latency: ", Latency)
# print("Prompt tokens: ", prompt_tokens)
# print("Completion tokens: ", completion_tokens)
# print("Total tokens: ", total_tokens)
# print("TPOT: ", TPOT)
# print("TPS: ", TPS)
# print(content)


# import openai

# client = openai.OpenAI(api_key="token-abc123", base_url="http://localhost:8000/v1")
# messages = [{"role": "user", "content": "count from 1 to 10."}]
# model = "meta-llama/Meta-Llama-3-8B-Instruct"
# max_tokens = 512
# stop = None
# extra_body = {}
# kwargs = {}

# response = client.chat.completions.create(
#     model=model,
#     messages=messages,
#     max_tokens=max_tokens,
#     stop=stop,
#     extra_body=extra_body,
#     **kwargs,
# )
# print(response.choices[0].message.to_dict()['content'])


# import openai

# client = openai.OpenAI(api_key="token-abc123", base_url="http://localhost:8000/v1")
# prompt = "count from 1 to 10."
# model = "meta-llama/Meta-Llama-3-8B-Instruct"
# max_tokens = 512
# stop = None
# extra_body = {}
# kwargs = {}

# response = client.completions.create(
#     model=model,
#     prompt=prompt,
#     max_tokens=max_tokens,
#     stop=stop,
#     extra_body=extra_body,
#     **kwargs,
# )
# print(response.choices[0].text)


class BasicPlanner(object):

    def __init__(self):
        super().__init__()
        self.debug_flag = 1

    def reset(
        self,
        model="google/gemma-1.1-2b-it",
        llm_type_force=None,
        api_key="token-abc123",
        parallel_size=1,
        nolaunch=True,
        port=8000,
    ):
        """
        :Description: Reset the server.
        :Param
            model: str, The model to use.
            api_key: str, The API key to use.
            parallel_size: int, The parallel size to use.
            nolaunch: bool, Whether to not launch the server.
        """
        self.model = model
        self.api_key = api_key
        self.parallel_size = parallel_size
        cmd = [
            "python",
            "-m",
            "vllm.entrypoints.openai.api_server",
            "--model",
            "{model}",
            "--dtype",
            "auto",
            "--api-key",
            "{api_key}",
            "--tensor-parallel-size",
            "{parallel_size}",
            "--trust-remote-code",
            "--disable-log-requests",
        ]
        if self.model == "microsoft/Phi-3-mini-128k-instruct" or self.model.startswith(
            "mosaicml"
        ):
            cmd.extend(["--max-model-len", "8192"])
        self.cmd = " ".join(cmd).format(
            model=model, api_key=api_key, parallel_size=parallel_size
        )
        logger = logging.getLogger()
        self.nolaunch = nolaunch
        if nolaunch:
            log.info("No launch!")
            self.pro = None
        else:
            log.info(f"Command: {self.cmd}")
            self.pro = subprocess.Popen(
                self.cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                shell=True,
                preexec_fn=os.setsid,
            )
        self.port = port
        self.llm_type_force = None
        logger.info(
            f"The model {self.model} is of type {self._decide_llm_type(self.model)}, {nolaunch = }"
        )
        self._decide_llm_type_force(llm_type_force)
        self.clear_usage()

    def clear_usage(self):
        """
        :Description
            Clear token counts.
        """
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.aTTFT = 0
        self.Latency = 0
        self.aTPOT = 0
        self.aTPS = 0
        self.epoch = 0

    def wait_for_start(self):
        """
        :Description
            Wait for the server to start.
        :Return
            bool, Whether the server has started.
        """
        if self.nolaunch:
            return True
        if self.pro is None:
            return False
        logger = logging.getLogger()
        while True:
            if self.pro.poll() is not None:
                logger.info("Server stopped!")
                return False
            line = self.pro.stderr.readline()
            line = line.decode("utf-8").rstrip()
            logger.error(f"Stderr: {line}")
            if line.count("Uvicorn running on") > 0:
                logger.info(f"Model {self.model} is running!")
                return True

    def _message2prompt(self, messages):
        """
        :Description
            Convert messages to prompt.
        :Param
            messages: list[dict[str, str]], A list of messages to chat with the model.
        :Return
            str, The prompt.
        """
        prompt = ""
        for message in messages:
            prompt += message["content"] + "\n"
        return prompt

    async def moa(
        self,
        reference_models,
        reference_ports,
        reference_messages,
        aggregate_model,
        aggregate_system_prompt,
        aggregate_method,
        guided_choice=[],
        prev_actions=[],
        prev_obs=[],
        **kwargs,
    ) -> str:
        async def async_gen(**kwargs_):
            return await asyncio.to_thread(self.gen, **kwargs_)

        async def async_score(**kwargs_):
            return await asyncio.to_thread(self.score, **kwargs_)

        assert len(reference_models) == len(reference_ports)
        assert len(prev_actions) == len(prev_obs)

        reference_results = await asyncio.gather(
            *[
                async_gen(model=model, port=port, messages=reference_messages, **kwargs)
                for model, port in zip(reference_models, reference_ports)
            ]
        )
        aggregate_messages = [
            {"role": "system", "content": aggregate_system_prompt},
            {
                "role": "user",
                "content": "\n".join(
                    f"reference_result_{i+1}:{e}"
                    for i, e in enumerate(reference_results)
                )
                + f"Previous steps: {','.join(prev_actions) if len(prev_actions) > 0 else 'None'}."
            },
        ]
        aggregate_result = await async_gen(
            model=aggregate_model, messages=aggregate_messages, **kwargs
        )
        aggregate_messages.extend(
            [
                {"role": "assistant", "content": aggregate_result},
                {
                    "role": "user",
                    "content": f"Now choose the best action and give your answer based on the above results.Do not add any additional content in your response.So the next step is: ",
                },
            ]
        )

        if self.debug_flag < 5:
            # print("reference_models: ", reference_models)
            # print("reference_ports: ", reference_ports)
            # print("reference_messages: ", reference_messages)
            # print("aggregate_model: ", aggregate_model)
            # print("aggregate_system_prompt: ", aggregate_system_prompt)
            # print("aggregate_method: ", aggregate_method)
            # print("kwargs: ", kwargs)
            # # print("guided_choice: ", guided_choice)
            for i in range(len(reference_results)):
                print(f"reference_result_{i}: ", reference_results[i])
            print("aggregate_result: ", aggregate_result)
            self.debug_flag += 1

        if aggregate_method == "gen":
            return await async_gen(
                model=aggregate_model, messages=aggregate_messages, **kwargs
            )
        elif aggregate_method == "score":
            assert guided_choice != []
            return await async_score(
                model=aggregate_model,
                messages=aggregate_messages,
                guided_choice=guided_choice,
                **kwargs,
            )
        else:
            raise ValueError(f"Invalid aggregate method: {aggregate_method}")

    def score(
        self,
        messages,
        guided_choice,
        stream=False,
        model=None,
        port=None,
        max_tokens=1024,
        **kwargs,
    ) -> str:
        if stream:
            content, usage = self._request(
                messages=messages,
                guided_choice=guided_choice,
                model=model,
                port=port,
                max_tokens=max_tokens,
                **kwargs,
            )
            self.cal_usage(usage)
        else:
            content = self._request(
                messages=messages,
                guided_choice=guided_choice,
                model=model,
                port=port,
                max_tokens=max_tokens,
                **kwargs,
            )

        return content

    def gen(
        self,
        messages,
        stream=False,
        stop=None,
        guided_regex=None,
        model=None,
        port=None,
        max_tokens=1024,
        **kwargs,
    ):
        if stream:
            content, usage = self._stream(
                messages=messages,
                stop=stop,
                guided_regex=guided_regex,
                model=model,
                port=port,
                max_tokens=max_tokens,
                **kwargs,
            )
            self.cal_usage(usage)
        else:
            content = self._request(
                messages=messages,
                stop=stop,
                guided_regex=guided_regex,
                model=model,
                port=port,
                max_tokens=max_tokens,
                **kwargs,
            )

        return content

    def cal_usage(self, usage):
        """
        :Description
            Calculate the usage.
        :Param
            usage: dict, The usage to calculate.
        """
        self.prompt_tokens += usage["prompt_tokens"]
        self.completion_tokens += usage["completion_tokens"]
        self.total_tokens += usage["total_tokens"]
        self.aTTFT = (self.aTTFT * self.epoch + usage["TTFT"]) / (self.epoch + 1)
        self.Latency += usage["Latency"]
        self.aTPOT = (self.aTPOT * self.epoch + usage["TPOT"]) / (self.epoch + 1)
        self.aTPS = (self.aTPS * self.epoch + usage["TPS"]) / (self.epoch + 1)
        self.epoch += 1

    def kill(self):
        """
        :Description
            Kill the server.
        """
        if self.pro is None:
            return
        os.killpg(os.getpgid(self.pro.pid), signal.SIGTERM)
        while self.pro.poll() is None:
            time.sleep(1)
            print("waiting for server to stop...")
        self.pro = None

    def _rectify(self, model, messages):
        if model.startswith("google/gemma") or model.startswith("mistralai"):
            if messages[0]["role"] == "system":
                messages[1]["content"] = (
                    messages[0]["content"] + "\n" + messages[1]["content"]
                )
                messages = messages[1:]
        return messages

    def _decide_llm_type(self, model: str):
        """
        :Description
            Decide the type of LLM to use.
        :Param
            model: str, The model to use.
        :Return
            str, The type of LLM to use.
        """
        if self.llm_type_force is not None:
            return self.llm_type_force
        if model.startswith("OpenAI/"):
            name = model.split("/")[1]
            if any([name.startswith(kw) for kw in OPENAI_COMPLETION_KWS]):
                return "completion"
            else:
                return "chat"
        if (
            model.lower().count("it") > 0
            or model.lower().count("chat") > 0
            or model.count("gpt") > 0
            or model.lower().count("instruct") > 0
        ):
            return "chat"
        else:
            return "completion"

    def _decide_llm_type_force(self, llm_type_force: Optional[str]):
        """
        :Description
            Force the LLM type to use.
        :Param
            llm_type_force: str, The LLM type to use.
        """
        self.llm_type_force = llm_type_force

    def _request(
        self,
        messages=[],
        prompt="",
        stop=None,
        guided_regex=None,
        guided_choice=None,
        model=None,
        port=None,
        max_tokens=1024,
        **kwargs,
    ):
        model_whole = model if model is not None else self.model
        if model_whole.startswith("OpenAI"):
            client = openai.OpenAI(
                base_url=self.cfg.planner.openai_base_url
            )  # provide OPENAI_API_KEY in env
            model = model_whole[model_whole.index("/") + 1 :]
        else:
            port = port if port is not None else self.port
            client = openai.OpenAI(
                api_key=self.api_key, base_url=f"http://localhost:{port}/v1"
            )
            model = model_whole
        extra_body = {}
        if guided_regex is not None:
            extra_body["guided_regex"] = guided_regex
        if guided_choice is not None:
            extra_body["guided_choice"] = guided_choice
        params = {
            "model": model,
            "max_tokens": max_tokens,
            "stop": stop,
            **kwargs,
        }
        if not model_whole.startswith("OpenAI"):
            params.update({"extra_body": extra_body})
        try:
            model_type = self._decide_llm_type(model_whole)
            if model_type == "chat":
                messages = copy.deepcopy(messages)
                messages = self._rectify(model, messages)
                log.debug(f"message: {messages}")
                response = client.chat.completions.create(messages=messages, **params)
                content = response.choices[0].message.to_dict()["content"]
            else:
                if prompt == "":
                    prompt = self._message2prompt(messages)
                log.debug(f"prompt: {prompt}")
                response = client.completions.create(prompt=prompt, **params)
                content = response.choices[0].text

        except Exception as e:
            raise Exception(
                f"Error in request: {e}, request = <begin>{messages}<end>, model = {model}, guided_regex = {guided_regex}, guided_choice = {guided_choice}, max_tokens = {max_tokens}, kwargs = {kwargs}"
            )

        log.debug(f"content: {content}")
        return content

    def _stream(
        self,
        messages=[],
        prompt="",
        stop=None,
        guided_regex=None,
        guided_choice=None,
        model=None,
        port=None,
        max_tokens=1024,
        **kwargs,
    ):
        model_whole = model if model is not None else self.model
        if model_whole.startswith("OpenAI"):
            client = openai.OpenAI(
                base_url=self.cfg.planner.openai_base_url
            )  # provide OPENAI_API_KEY in env
            # model = model_whole.split("/")[1]
            model = model_whole[model_whole.index("/") + 1 :]
        else:
            port = port if port is not None else self.port
            client = openai.OpenAI(
                api_key=self.api_key, base_url=f"http://localhost:{port}/v1"
            )
            model = model_whole
        extra_body = {}
        if guided_regex is not None:
            extra_body["guided_regex"] = guided_regex
        if guided_choice is not None:
            extra_body["guided_choice"] = guided_choice
        params = {
            "model": model,
            "stream": True,
            "stream_options": {"include_usage": True},
            "max_tokens": max_tokens,
            "stop": stop,
            **kwargs,
        }
        if not model_whole.startswith("OpenAI"):
            params.update({"extra_body": extra_body})
        try:
            model_type = self._decide_llm_type(model_whole)
            first_token = True
            content = ""
            if model_type == "chat":
                messages = copy.deepcopy(messages)
                messages = self._rectify(model, messages)
                log.debug(f"message: {messages}")
                stream = client.chat.completions.create(messages=messages, **params)
            else:
                if prompt == "":
                    prompt = self._message2prompt(messages)
                log.debug(f"prompt: {prompt}")
                stream = client.completions.create(prompt=prompt, **params)

            time0 = time.time()
            for chunk in stream:
                if first_token:
                    TTFT = time.time() - time0
                    first_token = False
                if chunk.usage:
                    Latency = time.time() - time0
                    prompt_tokens = chunk.usage.prompt_tokens
                    completion_tokens = chunk.usage.completion_tokens
                    total_tokens = chunk.usage.total_tokens
                if len(chunk.choices) > 0:
                    content += (
                        chunk.choices[0].delta.content
                        if model_type == "chat"
                        else chunk.choices[0].text
                    ) or ""

        except Exception as e:
            raise Exception(
                f"Error in request: {e}, request = <begin>{messages}<end>, model = {model}, guided_regex = {guided_regex}, guided_choice = {guided_choice}, max_tokens = {max_tokens}, kwargs = {kwargs}"
            )

        try:
            usage = {
                "TTFT": TTFT,
                "Latency": Latency,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "TPOT": (Latency - TTFT) / completion_tokens,
                "TPS": completion_tokens / Latency,
            }
        except Exception as e:
            log.warning(f"No usage available: {e}")
            usage = {
                "TTFT": 0,
                "Latency": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "TPOT": 0,
                "TPS": 0,
            }
        log.debug(f"content: {content}")
        return content, usage

    def __del__(self):
        self.kill()
