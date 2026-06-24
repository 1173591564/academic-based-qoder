import type { SkillInfo } from "../types";
import { EmptyState } from "./EmptyState";
import { Repeat, Zap, Cpu } from "lucide-react";

export function SkillPanel({
  skills,
  onSkillClick,
}: {
  skills: SkillInfo[];
  onSkillClick: (skill: SkillInfo) => void;
}) {
  return (
    <>
      <div className="sidebar-header">
        <span className="sidebar-title">技能 ({skills.length})</span>
      </div>
      <div className="skill-list">
        {skills.length > 0 ? (
          skills.map((skill) => (
            <div
              key={skill.name}
              className="skill-item"
              onClick={() => onSkillClick(skill)}
            >
              <span className="skill-icon">
                {skill.is_workflow ? (
                  <Repeat size={14} className="skill-icon-workflow" />
                ) : (
                  <Zap size={14} className="skill-icon-atomic" />
                )}
              </span>
              <div className="skill-info">
                <div className="skill-name">{skill.display_name}</div>
                {skill.description && (
                  <div className="skill-desc">{skill.description}</div>
                )}
              </div>
            </div>
          ))
        ) : (
          <EmptyState
            icon={Cpu}
            title="暂无可用技能"
            description="确保 MCP 服务已启动"
          />
        )}
      </div>
    </>
  );
}
