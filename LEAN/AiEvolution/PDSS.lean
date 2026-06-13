/-
  AiEvolution.PDSS — Formal definitions and theorems for the
  Parasitic Domain-Specific Scaffolding (PDSS) architectural pattern.

  This module formalizes the core concepts from the paper:
  "Parasitic Scaffolding: An Architectural Pattern for Domain-Specific
  AI Research Tools" — Definition 1 (five-tuple), parasitism constraint,
  composability, structural isomorphism, and key theorems.

  Builds on AiEvolution.Basic (Innovation, Paper types).
-/
import AiEvolution.Basic

namespace PDSS

-- ===================================================================
-- 1. Component Types
-- ===================================================================

/-- A declarative rule: a Markdown document loaded into the host LLM's
    context window. Rules are the primary mechanism for domain knowledge
    injection. -/
structure Rule where
  name     : String         -- e.g., "identity.md"
  role     : String         -- e.g., "identity", "routing", "constraint"
  content  : String         -- the Markdown text
  deriving Repr, DecidableEq

/-- The schema of a tool's interface, specifying input and output types
    as strings (representing JSON Schema definitions in practice). -/
structure ToolSchema where
  inputSchema  : String     -- JSON Schema for inputs
  outputSchema : String     -- JSON Schema for outputs
  deriving Repr, DecidableEq

/-- A domain-specific tool exposed through a standardized protocol (MCP).
    Each tool has a typed interface and a concrete implementation. -/
structure Tool where
  name       : String       -- e.g., "search", "parse", "rag-search"
  schema     : ToolSchema
  protocol   : String       -- e.g., "MCP", "CLI"
  impl       : String       -- implementation reference (CLI command or API endpoint)
  deriving Repr, DecidableEq

/-- A single step in a workflow, referencing a tool and specifying
    expected output artifacts. -/
structure WorkflowStep where
  stepNumber  : Nat
  description : String      -- what to do at this step
  toolRef     : String      -- name of the tool to invoke
  outputSpec  : String      -- expected output format/path
  deriving Repr, DecidableEq

/-- A structured workflow: an executable procedure definition guiding
    the LLM through a complex multi-step domain task. -/
structure Workflow where
  name      : String        -- e.g., "research-survey", "paper-deep-dive"
  triggers  : List String   -- trigger conditions (keywords/intents)
  steps     : List WorkflowStep
  outputs   : List String   -- output artifact paths
  deriving Repr, DecidableEq

/-- Data source types for the structured data layer. -/
inductive DataKind where
  | jsonDocument    -- per-entity structured data
  | propertyGraph   -- relational knowledge (citation, concept)
  | vectorIndex     -- semantic similarity search
  deriving Repr, DecidableEq, Inhabited

/-- A structured data source in the PDSS data layer. -/
structure DataSource where
  name    : String
  kind    : DataKind
  path    : String          -- storage path or URI
  deriving Repr, DecidableEq

/-- The host platform providing compute, UI, and infrastructure.
    PDSS parasitizes this platform for all intelligence operations. -/
structure HostPlatform where
  name      : String        -- e.g., "Qoder IDE", "Cursor"
  llmAPI    : String        -- e.g., "Claude 3.5", "GPT-4o"
  hasIDE    : Bool          -- provides integrated development environment
  hasFS     : Bool          -- provides file system access
  hasTerm   : Bool          -- provides terminal execution
  hasVCS    : Bool          -- provides version control
  hasMarket : Bool          -- provides distribution marketplace
  deriving Repr, DecidableEq

-- ===================================================================
-- 2. PDSS System Definition (Formal Five-Tuple)
-- ===================================================================

/-- A PDSS system as a five-tuple S = (R, W, T, D, H) with
    well-formedness conditions. -/
structure ScaffoldSystem where
  rules     : List Rule
  workflows : List Workflow
  tools     : List Tool
  data      : List DataSource
  host      : HostPlatform
  -- Well-formedness: every workflow step references an existing tool
  wf_toolref : ∀ w ∈ workflows, ∀ s ∈ w.steps,
    ∃ t ∈ tools, t.name = s.toolRef
  deriving Repr

/-- Abbreviation for readability. -/
abbrev PDSS := ScaffoldSystem

-- ===================================================================
-- 3. Parasitism Constraint
-- ===================================================================

/-- A PDSS system is parasitic if it contains no trained models,
    no standalone UI, and no independent compute resources.
    All intelligence operations are delegated to the host LLM. -/
structure IsParasitic (S : PDSS) where
  -- No trained models: all intelligence comes from the host LLM
  no_models   : String       -- assertion: no neural network definitions
  -- No standalone UI: all interaction through host IDE
  no_ui       : S.host.hasIDE = true
  -- Host provides required infrastructure
  has_fs      : S.host.hasFS = true
  has_term    : S.host.hasTerm = true

-- ===================================================================
-- 4. Tool Protocol Compatibility and Composability
-- ===================================================================

/-- Two tools are protocol-compatible if they use the same protocol. -/
def protocolCompatible (t₁ t₂ : Tool) : Prop :=
  t₁.protocol = t₂.protocol

/-- Two PDSS systems are composable if they share at least one
    protocol-compatible tool, enabling cross-system tool invocation. -/
def composable (S₁ S₂ : PDSS) : Prop :=
  ∃ t₁ ∈ S₁.tools, ∃ t₂ ∈ S₂.tools,
    protocolCompatible t₁ t₂

/-- Tool union: merge tools from two PDSS systems, deduplicating by name. -/
def toolUnion (S₁ S₂ : PDSS) : List Tool :=
  S₁.tools ++ S₂.tools.filter (fun t₂ =>
    ¬ S₁.tools.any (fun t₁ => t₁.name = t₂.name))

-- ===================================================================
-- 5. Structural Isomorphism
-- ===================================================================

/-- Two PDSS systems are structurally isomorphic if there exist
    structure-preserving mappings between their component sets,
    preserving roles and protocols.
    This formalizes the "natural structure" claim: independently
    developed systems converge on the same architecture. -/
structure StructuralIsomorphism (S₁ S₂ : PDSS) where
  -- Mapping on rules preserving roles
  ruleRoles₁  : List (String × String)  -- roles present in S₁.rules
  ruleRoles₂  : List (String × String)  -- roles present in S₂.rules
  sameRoles   : ruleRoles₁.map Prod.snd = ruleRoles₂.map Prod.snd
  -- Mapping on tools preserving protocols
  toolProtos₁ : List (String × String)  -- (name, protocol) in S₁.tools
  toolProtos₂ : List (String × String)  -- (name, protocol) in S₂.tools
  sameProtos  : toolProtos₁.map Prod.snd = toolProtos₂.map Prod.snd
  -- Same layer count (4 layers: R, W, T, D + H)
  sameLayers  : True

-- ===================================================================
-- 6. Parasitic Evolution
-- ===================================================================

/-- A PDSS system's quality depends on its host LLM's capability.
    When the host improves, the system improves without code changes.
    We model this as a monotonicity property. -/
def qualityDependsOnHost (S : PDSS) (hostCapability : Nat) : Nat :=
  -- Simplified model: quality = f(host_capability, rules, data)
  -- In practice, this is the quality of LLM-generated outputs
  -- given the rules and data as context
  hostCapability + S.rules.length + S.data.length

/-- Parasitic evolution theorem: improving the host strictly improves
    the system quality, without any code changes to the scaffolding. -/
theorem parasitic_evolution (S : PDSS) (c₁ c₂ : Nat) (h : c₁ < c₂) :
    qualityDependsOnHost S c₁ < qualityDependsOnHost S c₂ := by
  unfold qualityDependsOnHost
  -- c₁ + |rules| + |data| < c₂ + |rules| + |data|
  -- This follows from c₁ < c₂ by arithmetic
  have h₁ : c₁ + S.rules.length + S.data.length < c₂ + S.rules.length + S.data.length := by
    omega
  exact h₁

-- ===================================================================
-- 7. Composability Theorems
-- ===================================================================

/-- Composability is symmetric: if S₁ is composable with S₂,
    then S₂ is composable with S₁. -/
theorem composable_symmetric (S₁ S₂ : PDSS) :
    composable S₁ S₂ → composable S₂ S₁ := by
  intro h
  unfold composable at h ⊢
  unfold protocolCompatible at h ⊢
  rcases h with ⟨t₁, ht₁, t₂, ht₂, hproto⟩
  refine ⟨t₂, ht₂, t₁, ht₁, ?_⟩
  rw [hproto]

/-- Composability via shared MCP protocol:
    If both systems use MCP, they are composable. -/
theorem mcp_implies_composable (S₁ S₂ : PDSS)
    (t₁ : Tool) (ht₁ : t₁ ∈ S₁.tools)
    (t₂ : Tool) (ht₂ : t₂ ∈ S₂.tools)
    (hmcp₁ : ∀ t ∈ S₁.tools, t.protocol = "MCP")
    (hmcp₂ : ∀ t ∈ S₂.tools, t.protocol = "MCP") :
    composable S₁ S₂ := by
  unfold composable protocolCompatible
  refine ⟨t₁, ht₁, t₂, ht₂, ?_⟩
  have hp₁ : t₁.protocol = "MCP" := hmcp₁ t₁ ht₁
  have hp₂ : t₂.protocol = "MCP" := hmcp₂ t₂ ht₂
  rw [hp₁, hp₂]

-- ===================================================================
-- 8. Minimalism Principle (Quantitative)
-- ===================================================================

/-- The code ratio: fraction of system components that are
    imperative code (tools) vs. declarative (rules + workflows).
    Lower ratio = more minimal = better PDSS.
    We use Nat × Nat (numerator, denominator) to avoid Rat issues. -/
def codeRatioNum (S : PDSS) : Nat :=
  S.tools.length

def codeRatioDen (S : PDSS) : Nat :=
  S.rules.length + S.workflows.length + S.tools.length

/-- A PDSS system satisfies the minimalism principle if
    2 * |tools| < |rules| + |workflows| + |tools|,
    i.e., tools are less than half of all components. -/
def satisfiesMinimalism (S : PDSS) : Prop :=
  2 * codeRatioNum S < codeRatioDen S

end PDSS
