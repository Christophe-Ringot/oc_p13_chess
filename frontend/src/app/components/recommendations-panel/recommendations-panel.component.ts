import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { OpeningMove, RecommendationsState } from '../../models/chess.models';
import { MarkdownPipe } from '../../pipes/markdown.pipe';

@Component({
  selector: 'app-recommendations-panel',
  standalone: true,
  imports: [CommonModule, MarkdownPipe],
  templateUrl: './recommendations-panel.component.html',
})
export class RecommendationsPanelComponent {
  @Input({ required: true }) state!: RecommendationsState;
  @Output() playMove = new EventEmitter<string>();
  @Output() retry = new EventEmitter<void>();

  winRate(move: OpeningMove): number {
    return move.games > 0 ? Math.round((move.white / move.games) * 100) : 0;
  }

  drawRate(move: OpeningMove): number {
    return move.games > 0 ? Math.round((move.draws / move.games) * 100) : 0;
  }

  lossRate(move: OpeningMove): number {
    return move.games > 0 ? Math.round((move.black / move.games) * 100) : 0;
  }

  scoreLabel(scoreType: string | null, score: number | null): string {
    if (score === null || !scoreType) {
      return '—';
    }
    if (scoreType === 'mate') {
      return `Mat en ${Math.abs(score)} (${score > 0 ? 'blancs' : 'noirs'})`;
    }
    const pawns = (score / 100).toFixed(2);
    return `${score > 0 ? '+' : ''}${pawns}`;
  }
}
