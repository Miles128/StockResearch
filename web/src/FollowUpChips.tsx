interface FollowUpChipsProps {
  questions: string[];
  onSelect: (query: string) => void;
}

export function FollowUpChips({ questions, onSelect }: FollowUpChipsProps) {
  if (!questions.length) return null;
  return (
    <div className="follow-up-row">
      {questions.map((question) => (
        <button key={question} type="button" className="example-chip" onClick={() => onSelect(question)}>
          {question}
        </button>
      ))}
    </div>
  );
}
