from agents import Agent, Runner, model_settings

agent = Agent(name="Assistant", instructions="你是一个有用的人工智能助手")
result = Runner.run_sync(agent, "Write a haiku about recursion in programming.")
print(result.final_output)
