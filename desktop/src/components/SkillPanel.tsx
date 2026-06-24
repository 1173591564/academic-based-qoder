import type { SkillInfo } from "../types";

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
                {skill.is_workflow ? "🔄" : "⚡"}
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
          <div className="empty-hint">暂无技能</div>
        )}
      </div>
    </>
  );
}
