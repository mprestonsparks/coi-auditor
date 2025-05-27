# Optimizing Instructions for Roo: A Guide for External Experts

This document provides guidance on how to structure information and instructions for Roo, an AI workflow orchestrator, to ensure maximum effectiveness and efficient task completion. Understanding Roo's processing mechanisms and the capabilities of its underlying language model will help you provide input that Roo can best utilize.

## I. Roo-Specific Information: How Roo Works

Roo is a strategic workflow orchestrator designed to coordinate complex tasks by delegating them to appropriate specialized modes. My primary function is to understand your high-level goals, break them down into manageable subtasks, and assign those subtasks to the mode best equipped to handle them.

### A. Information Processing and Task Execution

1.  **Iterative Approach:** I operate on an iterative, step-by-step basis. I receive a task, analyze it, and then typically use a tool (e.g., read a file, execute a command, switch modes, or delegate a subtask). I then wait for the result of that tool use before deciding on the next step. This allows for course correction and adaptation based on new information.
2.  **Tool-Driven Actions:** My actions are primarily driven by a set of available tools. These include file operations (read, write, diff, list), command execution, code definition listing, regex search, asking follow-up questions, and delegating new tasks.
3.  **Context is Key:** I rely heavily on the context provided. This includes the initial task description, file contents, terminal outputs, previous conversation history, and environment details (like file structure and OS). The more comprehensive and clear the context, the better I can perform. The project base directory is currently `c:/Users/Butle/Desktop/Preston/gitRepos/coi-auditor`.
4.  **Subtask Delegation:** For complex requests, especially those requiring different types of expertise or significant shifts in focus, I use the `new_task` tool to delegate to specialized modes. When doing so, I provide detailed instructions and context to the subtask, including an explicit statement that the subtask should signal completion using the `attempt_completion` tool.
5.  **Completion and Feedback:** Once I believe a task (or subtask) is complete, I use the `attempt_completion` tool. User feedback on this attempt is crucial for refinement.

### B. Preferences for Instruction Structure

To help me understand and execute your instructions most effectively, please consider the following:

1.  **Clarity and Specificity:**
    *   Provide clear, unambiguous instructions.
    *   Define the scope of the task precisely. What should be done, and just as importantly, what should *not* be done?
    *   If providing code or diffs, ensure they are complete and contextually accurate (e.g., correct line numbers, full function bodies if replacing). Use the diff format I use if possible (SEARCH/REPLACE blocks with line numbers).
2.  **Step-by-Step Breakdown (for complex instructions to Roo directly):**
    *   If you are guiding Roo (as Orchestrator) through a multi-step process that *doesn't* involve immediate delegation, breaking it down into logical steps can be helpful. However, for complex coding or analysis, it's often better to provide a high-level goal and let me delegate it.
3.  **Contextual Information:**
    *   Always provide necessary file paths (relative to the project root: `c:/Users/Butle/Desktop/Preston/gitRepos/coi-auditor`).
    *   Reference specific function names (`language.declaration()`), line numbers, or error messages when discussing code.
    *   If providing logs or outputs, include enough surrounding information for context.
4.  **Explicit Goals for Subtasks:**
    *   When you anticipate Roo will delegate (or if you are providing instructions *for* a subtask that Roo will create), clearly state the subtask's objective, its inputs, and its expected output or completion signal (e.g., "The subtask should use `attempt_completion` with a summary of X").
5.  **Error Handling and Debugging Information:**
    *   If you are providing a plan to fix an error, explain the suspected root cause.
    *   Suggest specific debugging steps or logging to add.
    *   Provide expected outcomes for any commands or code changes.

### C. Roo's Specialized Modes

Understanding my modes will help you tailor instructions, especially when you anticipate a task will be delegated.

1.  **`💻 Code` Mode (`code`):**
    *   **Role:** A highly skilled software engineer.
    *   **Capabilities:** Writing new code, modifying existing code (applying diffs, writing files, inserting content, search/replace), understanding programming languages, frameworks, design patterns, and best practices. Can use all file operation tools and execute commands.
    *   **Expert Input:** Provide specific coding tasks, bug fixes, refactoring instructions, or feature implementation details. Diff patches are highly effective.
2.  **`🏗️ Architect` Mode (`architect`):**
    *   **Role:** An experienced technical leader, planner, and inquisitor.
    *   **Capabilities:** High-level planning, system design, documentation (typically Markdown files), defining project structure, and breaking down complex problems. More restricted in file editing (e.g., can usually only edit `.md` files).
    *   **Expert Input:** Ask for architectural plans, documentation outlines, or high-level strategies for tackling complex technical challenges.
3.  **`❓ Ask` Mode (`ask`):**
    *   **Role:** A knowledgeable technical assistant.
    *   **Capabilities:** Answering questions about software development, technology, specific code (if provided context), and general technical topics. Does not typically perform file modifications or command executions.
    *   **Expert Input:** If the expert's report contains conceptual explanations or requires Roo to understand a new technology, this mode might be used internally by Roo to process that information.
4.  **`🪲 Debug` Mode (`debug`):**
    *   **Role:** An expert software debugger.
    *   **Capabilities:** Systematic problem diagnosis, analyzing logs, stepping through code (conceptually), and proposing fixes. Utilizes tools to inspect code, logs, and execute diagnostic commands.
    *   **Expert Input:** Provide detailed error reports, logs, and code snippets. Suggest specific debugging steps or hypotheses to test.
5.  **`🪃 Orchestrator` Mode (`orchestrator`):** (This is the mode Roo uses to coordinate and delegate)
    *   **Role:** Strategic workflow coordinator.
    *   **Capabilities:** Breaking down complex user requests into subtasks, delegating those subtasks to the appropriate specialized modes using the `new_task` tool, managing workflow, and synthesizing results. Does not directly write code or perform deep technical analysis itself but relies on other modes.
    *   **Expert Input:** Your report will be received by me (Roo) likely in Orchestrator mode. I will then analyze your plan and delegate its execution steps to other modes (e.g., `Code` or `Debug` mode). Therefore, structure your plan as a series of actionable steps that I can translate into subtask instructions. Clearly indicate which mode might be best for each step if you have a strong opinion. Your understanding that I can handle complex, multi-step plans via delegation is key.

By understanding these modes, you can provide instructions that are not only clear but also anticipate how I might delegate parts of the work, leading to a more efficient resolution.

## II. Model-Specific Information: `gemini-2.5-pro-preview-03-25`

While Roo provides an orchestration layer, the underlying language model (`gemini-2.5-pro-preview-03-25`) has its own characteristics that influence how information is processed.

### A. Token Processing and Context Window

1.  **Input/Output Tokens:** Like all LLMs, Gemini processes information in "tokens" (roughly words or parts of words). There's a limit to the number of tokens that can be processed in a single input (prompt) and generated in a single output (response). This is known as the context window.
    *   **Current Context Size:** The `environment_details` often includes a "Current Context Size (Tokens)" value. While I strive to manage this, extremely long inputs or histories can approach this limit.
    *   **Implication for Expert:** Be concise yet comprehensive. If providing large code blocks or logs, ensure they are directly relevant. Summaries can be helpful if full context is excessively large, but always prioritize providing enough detail for accurate diagnosis.
2.  **Information Retention:** The model "remembers" information from the current session's conversation history (up to its context window limit). Information from earlier in the conversation is generally available, but very distant information might have less influence or could be truncated if the context window is exceeded.
    *   **Implication for Expert:** If referring to information provided much earlier, a brief re-statement or clear reference can be beneficial.

### B. Reasoning and Instruction Following

1.  **Chain of Thought/Reasoning:** Gemini models, especially advanced ones like 2.5 Pro, can perform complex reasoning. Providing a clear "chain of thought" or step-by-step logic in your explanations can help the model (and thus Roo) understand the rationale behind your suggestions.
    *   **Implication for Expert:** When explaining a diagnosis or solution, walk through the reasoning. This helps me learn and apply the logic more effectively. My own `<thinking>` blocks are a form of this.
2.  **Instruction Adherence:** Gemini 2.5 Pro is generally good at following instructions. However, very complex, multi-faceted, or subtly contradictory instructions can sometimes lead to parts being overlooked or misinterpreted.
    *   **Implication for Expert:**
        *   Use clear, direct language.
        *   Bullet points or numbered lists for multi-step instructions are highly effective.
        *   If an instruction has multiple components, ensure each is distinct.
        *   Explicitly stating constraints or what *not* to do can be as important as stating what *to* do.
3.  **Handling Ambiguity:** While the model can make inferences, it performs best with unambiguous input.
    *   **Implication for Expert:** Minimize jargon where simpler terms suffice (unless it's standard technical terminology essential for precision). Define any non-standard terms or assumptions.

### C. Output Generation

1.  **Structured Output:** The model can generate structured output (e.g., code blocks, JSON, Markdown) when prompted to do so.
    *   **Implication for Expert:** If you want code changes, providing them in diff format or as complete code blocks is ideal. If you're suggesting a plan, a numbered or bulleted list is excellent.
2.  **Verbosity and Detail:** The model can be adjusted for verbosity. For debugging and planning, a moderate to high level of detail in your explanations is generally preferred by Roo.
    *   **Implication for Expert:** Don't skimp on explaining the "why" behind your suggestions.

## III. General Recommendations for the Expert's Report

1.  **Start with a Summary/Overview:** A brief executive summary of your findings and the overall proposed plan can be very helpful for Roo to quickly grasp the main points before diving into details.
2.  **Prioritize Actions:** If your plan involves multiple steps, indicate any priorities or dependencies between them.
3.  **Reference Provided Materials:** Clearly refer back to specific sections of the report Roo generated for you (e.g., "Regarding Problem III.C in `coding-help-20250522-1451.md`," or "In the `extract_raw_ocr_text_from_pdf` function (Section IV.A of that report)..."). This helps Roo link your advice directly to the context.
4.  **Be Explicit About Assumptions:** If you make any assumptions while formulating your plan, please state them.
5.  **Focus on Actionable Steps:** While understanding the theory is good, the primary goal is a plan that Roo can execute. Ensure your recommendations translate into concrete actions Roo can take (e.g., "Modify file X with this diff," "Add these log statements," "Execute command Y and check for output Z").
6.  **Markdown Formatting:** Please use markdown for your report, as it's the format Roo is most adept at parsing and displaying, especially for code blocks and structured lists.

By following this guidance, you can help Roo make the best possible use of your expertise, leading to a faster and more effective resolution of the current issues. Roo looks forward to your insights!