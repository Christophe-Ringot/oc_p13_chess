export interface OpeningMove {
  uci: string | null;
  san: string | null;
  games: number;
  white: number;
  draws: number;
  black: number;
  average_rating: number | null;
}

export interface Opening {
  eco: string | null;
  name: string | null;
}

export interface MovesResponse {
  fen: string;
  database: string;
  opening: Opening | null;
  total_games: number;
  theoretical: boolean;
  moves: OpeningMove[];
}

export interface EvaluateResponse {
  fen: string;
  score_type: string | null;
  score: number | null;
  best_move: string | null;
  depth: number;
  side_to_move: string;
}

export interface VectorSearchResult {
  text: string;
  opening: string | null;
  source: string | null;
  score: number;
}

export interface VideoResult {
  video_id: string;
  title: string;
  channel: string | null;
  description: string | null;
  published_at: string | null;
  thumbnail_url: string | null;
  view_count: number | null;
  url: string;
  embed_url: string;
}

export interface VectorSearchResponse {
  query: string;
  results: VectorSearchResult[];
  videos: VideoResult[];
}

export interface Evaluation {
  score_type: string | null;
  score: number | null;
  best_move: string | null;
  depth: number;
  side_to_move: string;
}

export interface AgentAnalysisResponse {
  fen: string;
  theoretical: boolean;
  opening: Opening | null;
  total_games: number;
  moves: OpeningMove[];
  evaluation: Evaluation | null;
  results: VectorSearchResult[];
  videos: VideoResult[];
  tools_used: string[];
}

export interface AsyncSection<T> {
  loading: boolean;
  error: string | null;
  data: T | null;
}

export interface RagAnswerState {
  loading: boolean;
  streaming: boolean;
  error: string | null;
  text: string;
}

export type RagStreamEvent =
  | { type: 'sources'; data: VectorSearchResponse }
  | { type: 'delta'; text: string }
  | { type: 'error'; message: string }
  | { type: 'done' };

export type AgentStepStatus = 'ok' | 'error' | 'skipped';

export interface AgentStep {
  step: string;
  label: string;
  status: AgentStepStatus;
  detail: string;
}

export type AgentAnalysisEvent =
  | { type: 'step'; step: AgentStep }
  | { type: 'done'; data: AgentAnalysisResponse };

export interface RecommendationsState {
  moves: AsyncSection<MovesResponse>;
  evaluation: AsyncSection<EvaluateResponse>;
  context: AsyncSection<VectorSearchResponse>;
  answer: RagAnswerState;
  steps: AgentStep[];
  streamingSteps: boolean;
}

export function emptySection<T>(): AsyncSection<T> {
  return { loading: false, error: null, data: null };
}

export function emptyRagAnswerState(): RagAnswerState {
  return { loading: false, streaming: false, error: null, text: '' };
}

export function emptyRecommendationsState(): RecommendationsState {
  return {
    moves: emptySection<MovesResponse>(),
    evaluation: emptySection<EvaluateResponse>(),
    context: emptySection<VectorSearchResponse>(),
    answer: emptyRagAnswerState(),
    steps: [],
    streamingSteps: false,
  };
}
