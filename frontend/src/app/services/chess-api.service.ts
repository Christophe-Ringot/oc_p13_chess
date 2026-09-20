import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import {
  AgentAnalysisEvent,
  RagStreamEvent,
  VectorSearchResult,
  VideoResult,
} from '../models/chess.models';

@Injectable({ providedIn: 'root' })
export class ChessApiService {
  private readonly baseUrl = environment.apiUrl;

  constructor(private readonly http: HttpClient) {}

  analyzePositionStream(
    fen: string,
    database?: string,
  ): Observable<AgentAnalysisEvent> {
    let params = new HttpParams().set('fen', fen);
    if (database) {
      params = params.set('database', database);
    }
    const url = `${this.baseUrl}/agent/stream?${params.toString()}`;

    return new Observable<AgentAnalysisEvent>((subscriber) => {
      const source = new EventSource(url);

      source.addEventListener('step', (event) => {
        subscriber.next({
          type: 'step',
          step: JSON.parse((event as MessageEvent).data),
        });
      });
      source.addEventListener('done', (event) => {
        subscriber.next({
          type: 'done',
          data: JSON.parse((event as MessageEvent).data),
        });
        subscriber.complete();
        source.close();
      });
      source.onerror = () => {
        subscriber.error(new Error('Connexion au flux interrompue.'));
        source.close();
      };

      return () => source.close();
    });
  }

  streamOpeningAnswer(
    opening: string,
    context: { results: VectorSearchResult[]; videos: VideoResult[] },
  ): Observable<RagStreamEvent> {
    return new Observable<RagStreamEvent>((subscriber) => {
      const controller = new AbortController();

      fetch(`${this.baseUrl}/agent/answer/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          opening,
          results: context.results,
          videos: context.videos,
        }),
        signal: controller.signal,
      })
        .then(async (response) => {
          if (!response.ok || !response.body) {
            throw new Error(`Erreur serveur (${response.status}).`);
          }
          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const events = buffer.split('\n\n');
            buffer = events.pop() ?? '';

            for (const raw of events) {
              const eventLine = raw
                .split('\n')
                .find((line) => line.startsWith('event: '));
              const dataLine = raw
                .split('\n')
                .find((line) => line.startsWith('data: '));
              if (!eventLine || !dataLine) {
                continue;
              }
              const type = eventLine.slice('event: '.length);
              const payload = JSON.parse(dataLine.slice('data: '.length));

              if (type === 'sources') {
                subscriber.next({ type: 'sources', data: payload });
              } else if (type === 'delta') {
                subscriber.next({ type: 'delta', text: payload.text });
              } else if (type === 'llm_error') {
                subscriber.next({ type: 'error', message: payload.message });
              } else if (type === 'done') {
                subscriber.next({ type: 'done' });
                subscriber.complete();
              }
            }
          }
        })
        .catch((err) => {
          if (controller.signal.aborted) {
            return;
          }
          subscriber.error(
            err instanceof Error
              ? err
              : new Error('Connexion au flux interrompue.'),
          );
        });

      return () => controller.abort();
    });
  }
}
