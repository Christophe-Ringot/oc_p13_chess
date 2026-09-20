import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnDestroy, OnInit } from '@angular/core';
import {
  Observable,
  Subject,
  Subscription,
  catchError,
  concat,
  debounceTime,
  distinctUntilChanged,
  map,
  merge,
  of,
  scan,
  switchMap,
  tap,
} from 'rxjs';
import { AgentStepsComponent } from './components/agent-steps/agent-steps.component';
import { ChessboardComponent, START_FEN } from './components/chessboard/chessboard.component';
import { RecommendationsPanelComponent } from './components/recommendations-panel/recommendations-panel.component';
import {
  AgentAnalysisResponse,
  AgentStep,
  RagAnswerState,
  RecommendationsState,
  VectorSearchResult,
  VideoResult,
  emptyRagAnswerState,
  emptyRecommendationsState,
} from './models/chess.models';
import { ChessApiService } from './services/chess-api.service';

interface StepAccumulator {
  done: boolean;
  steps: AgentStep[];
  data: AgentAnalysisResponse | null;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [ChessboardComponent, RecommendationsPanelComponent, AgentStepsComponent],
  templateUrl: './app.component.html',
})
export class AppComponent implements OnInit, OnDestroy {
  state: RecommendationsState = emptyRecommendationsState();

  private readonly fen$ = new Subject<string>();
  private readonly retry$ = new Subject<void>();
  private currentFen = START_FEN;
  private subscription?: Subscription;

  constructor(private readonly api: ChessApiService) {}

  get isLoading(): boolean {
    return this.state.moves.loading || this.state.evaluation.loading;
  }

  ngOnInit(): void {
    this.subscription = merge(
      this.fen$.pipe(distinctUntilChanged(), debounceTime(300)),
      this.retry$.pipe(map(() => this.currentFen))
    )
      .pipe(
        tap((fen) => (this.currentFen = fen)),
        switchMap((fen) => this.buildRecommendations(fen))
      )
      .subscribe((state) => (this.state = state));

    this.fen$.next(START_FEN);
  }

  ngOnDestroy(): void {
    this.subscription?.unsubscribe();
  }

  onFenChange(fen: string): void {
    this.fen$.next(fen);
  }

  onRetry(): void {
    this.retry$.next();
  }

  private buildRecommendations(fen: string): Observable<RecommendationsState> {
    const loadingState: RecommendationsState = {
      moves: { loading: true, error: null, data: null },
      evaluation: { loading: true, error: null, data: null },
      context: { loading: false, error: null, data: null },
      answer: emptyRagAnswerState(),
      steps: [],
      streamingSteps: true,
    };

    // Un seul flux SSE : l'agent (LangGraph) decide lui-meme, a partir du
    // FEN, quelles etapes executer (Lichess/Stockfish toujours, puis
    // Wikichess/YouTube seulement si la position est theorique et une
    // ouverture identifiee). Chaque etape est emise au fur et a mesure pour
    // visualiser la progression de l'agent. Voir backend/app/services/rag_graph.py.
    const analysis$ = this.api.analyzePositionStream(fen).pipe(
      scan(
        (acc, event): StepAccumulator =>
          event.type === 'step'
            ? { ...acc, steps: [...acc.steps, event.step] }
            : { ...acc, done: true, data: event.data },
        { done: false, steps: [], data: null } as StepAccumulator
      ),
      switchMap((acc) => {
        if (!acc.done || !acc.data) {
          return of<RecommendationsState>({ ...loadingState, steps: acc.steps, streamingSteps: true });
        }

        const analysis = acc.data;
        const openingName = analysis.opening?.name ?? null;

        const baseState: RecommendationsState = {
          moves: {
            loading: false,
            error: null,
            data: {
              fen,
              database: '',
              opening: analysis.opening,
              total_games: analysis.total_games,
              theoretical: analysis.theoretical,
              moves: analysis.moves,
            },
          },
          evaluation: analysis.evaluation
            ? { loading: false, error: null, data: { fen, ...analysis.evaluation } }
            : { loading: false, error: 'Évaluation Stockfish indisponible.', data: null },
          context:
            analysis.theoretical && openingName
              ? {
                  loading: false,
                  error: null,
                  data: { query: openingName, results: analysis.results, videos: analysis.videos },
                }
              : { loading: false, error: null, data: null },
          answer:
            analysis.theoretical && openingName
              ? { ...emptyRagAnswerState(), loading: true }
              : emptyRagAnswerState(),
          steps: acc.steps,
          streamingSteps: false,
        };

        if (!analysis.theoretical || !openingName) {
          return of(baseState);
        }

        const answer$ = this.buildAnswer(openingName, analysis.results, analysis.videos).pipe(
          map((answer) => ({ ...baseState, answer }))
        );

        return concat(of(baseState), answer$);
      }),
      catchError((err) => {
        const message = this.errorMessage(err);
        return of<RecommendationsState>({
          ...loadingState,
          streamingSteps: false,
          moves: { loading: false, error: message, data: null },
          evaluation: { loading: false, error: message, data: null },
        });
      })
    );

    return concat(of(loadingState), analysis$);
  }

  private buildAnswer(
    opening: string,
    results: VectorSearchResult[],
    videos: VideoResult[]
  ): Observable<RagAnswerState> {
    const initial: RagAnswerState = { ...emptyRagAnswerState(), loading: true };

    const streamed$ = this.api.streamOpeningAnswer(opening, { results, videos }).pipe(
      scan((acc, event): RagAnswerState => {
        switch (event.type) {
          case 'sources':
            return acc;
          case 'delta':
            return { loading: false, streaming: true, error: null, text: acc.text + event.text };
          case 'error':
            return { ...acc, loading: false, streaming: false, error: event.message };
          case 'done':
            return { ...acc, loading: false, streaming: false };
        }
      }, initial),
      catchError((err) => of<RagAnswerState>({ loading: false, streaming: false, error: this.errorMessage(err), text: '' }))
    );

    return concat(of(initial), streamed$);
  }

  private errorMessage(err: unknown): string {
    if (err instanceof HttpErrorResponse) {
      if (err.status === 0) {
        return 'Impossible de contacter le serveur.';
      }
      const detail = (err.error as { detail?: string } | null)?.detail;
      return detail || `Erreur serveur (${err.status}).`;
    }
    return 'Erreur inconnue.';
  }
}
