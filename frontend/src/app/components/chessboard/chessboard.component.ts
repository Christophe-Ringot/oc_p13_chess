import { Component, EventEmitter, Input, Output, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  MoveChange,
  NgxChessBoardComponent,
  NgxChessBoardModule,
} from 'ngx-chess-board';

export const START_FEN =
  'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

@Component({
  selector: 'app-chessboard',
  standalone: true,
  imports: [FormsModule, NgxChessBoardModule],
  templateUrl: './chessboard.component.html',
})
export class ChessboardComponent {
  @Input() disabled = false;
  @Output() fenChange = new EventEmitter<string>();

  @ViewChild('board') board!: NgxChessBoardComponent;

  fenInput = '';
  loadError = '';

  onMoveChange(change: MoveChange): void {
    this.fenChange.emit(change.fen);
  }

  reset(): void {
    this.board.reset();
    this.fenChange.emit(this.board.getFEN());
  }

  undo(): void {
    this.board.undo();
    this.fenChange.emit(this.board.getFEN());
  }

  flip(): void {
    this.board.reverse();
  }

  loadFen(): void {
    if (!this.fenInput.trim()) {
      return;
    }
    try {
      this.board.setFEN(this.fenInput.trim());
      this.loadError = '';
      this.fenChange.emit(this.board.getFEN());
    } catch {
      this.loadError = 'FEN invalide.';
    }
  }

  playMove(uci: string): void {
    this.board.move(uci);
  }
}
