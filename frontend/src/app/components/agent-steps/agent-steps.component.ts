import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { AgentStep } from '../../models/chess.models';

@Component({
  selector: 'app-agent-steps',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './agent-steps.component.html',
})
export class AgentStepsComponent {
  @Input() steps: AgentStep[] = [];
  @Input() streaming = false;
}
