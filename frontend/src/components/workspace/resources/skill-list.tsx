"use client";

import { useSkills } from "@/core/skills";

export function SkillList() {
  const { skills, isLoading } = useSkills();

  if (isLoading) {
    return <div className="text-muted-foreground">Loading...</div>;
  }

  if (!skills || skills.length === 0) {
    return <div className="text-muted-foreground">No skills found</div>;
  }

  return (
    <div className="workbench-resource-grid grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
      {skills.map((skill) => (
        <div
          key={skill.name}
          className="workbench-resource-card rounded-lg border p-4"
        >
          <h3 className="font-medium">{skill.name}</h3>
          <p className="text-muted-foreground text-base">{skill.description}</p>
        </div>
      ))}
    </div>
  );
}
