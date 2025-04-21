import streamlit as st
import os
from dotenv import load_dotenv
from tavily import TavilyClient
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, Tool
from langchain.agents import create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import END, Graph


load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",  
    temperature=0.7,
    google_api_key=GOOGLE_API_KEY
)


tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

def tavily_search(query: str):
    try:
        result = tavily_client.search(
            query=query,
            search_depth="advanced",
            include_raw_content=True
        )
        return str(result)
    except Exception as e:
        return f"Error searching Tavily: {str(e)}"


tavily_tool = Tool(
    name="tavily_search",
    func=tavily_search,
    description="A premium search engine that returns high-quality, up-to-date information."
)


def create_researcher_agent():
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a senior research analyst. Your job:
1. Use Tavily for authoritative info.
2. Cross-validate across multiple sources.
3. Extract key facts, stats & quotes.
4. Always include source URLs."""),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])
    agent = create_tool_calling_agent(llm, [tavily_tool], prompt)
    return AgentExecutor(agent=agent, tools=[tavily_tool])


def generate_final_report(research_output: str) -> str:
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a technical writer. Structure and present the research:
- Use markdown formatting
- Academic tone
- Include proper citations
- Highlight insights.
- Make sure to answer the user's original query completely."""), 
        ("user", "{input}")
    ])
    formatted_prompt = prompt.format_messages(input=research_output)
    return llm.invoke(formatted_prompt).content


def create_workflow():
    workflow = Graph()

    def research_node(state):
        agent = create_researcher_agent()
        output = agent.invoke({"input": state["query"], "agent_scratchpad": []})
        return {"research_output": output["output"]}

    def write_node(state):
        report = generate_final_report(state["research_output"])
        return {"final_report": report}

    workflow.add_node("research", research_node)
    workflow.add_node("write", write_node)
    workflow.add_edge("research", "write")
    workflow.add_edge("write", END)
    workflow.set_entry_point("research")
    return workflow


def main():
    st.set_page_config(page_title="AI Research Assistant", page_icon="🔍", layout="wide")
    st.title("🔍 AI Research Assistant")
    st.markdown("""Enter a query and let the AI prepare a research-backed report:
- Searches authoritative sources
- Validates information
- Delivers a professional markdown report.
""")

    query = st.text_area("Enter your research query:",
                         placeholder="e.g., 'Impact of AI on healthcare jobs in 2024'",
                         height=100)

    if st.button("Research", type="primary"):
        if not query:
            st.warning("Please enter a research query first.")
            return

        if not GOOGLE_API_KEY or not TAVILY_API_KEY:
            st.error(" API keys missing! Check your `.env` file.")
            return

        with st.spinner("Researching your topic..."):
            try:
                workflow = create_workflow()
                app = workflow.compile()
                
                
                final_output = app.invoke({"query": query})
                
                
                with st.expander(" Research Report", expanded=True):
                    if "final_report" in final_output:
                        st.markdown(final_output["final_report"])
                    elif "research_output" in final_output:
                        st.markdown("### Research Findings (Unformatted)")
                        st.markdown(final_output["research_output"])
                    else:
                        st.warning("No results were generated")

                st.success(" Research completed!")

            except Exception as e:
                st.error(f" An error occurred: {str(e)}")
                st.exception(e)


if __name__ == "__main__":
    main()