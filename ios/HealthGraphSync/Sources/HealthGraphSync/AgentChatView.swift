import SwiftUI

struct AgentChatView: View {
    @State private var question: String = ""
    @State private var history: [QAEntry] = QAEntry.loadHistory()
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var expandedEntry: QAEntry?

    private static let suggestions: [Suggestion] = [
        Suggestion(label: "Last week summary") {
            let (start, end) = lastWeekRange()
            return """
            Summarize my health from \(start) to \(end) (last ISO week). \
            Report average resting heart rate, HRV, daily steps, sleep hours, \
            and total workout minutes. Compare each to my 30-day baseline and \
            flag changes with arrows (↑ improving, ↓ declining, → stable).
            """
        },
        Suggestion(label: "Overtraining check") {
            "Am I overtraining? Use the overtraining_check tool to look at training load vs HRV over the last 12 weeks. Flag weeks with CAUTION or HIGH RISK and recommend deload weeks if needed."
        },
        Suggestion(label: "Best workout day") {
            let (start, end) = lastNDaysRange(30)
            return "Between \(start) and \(end), which workout type gave me the best next-day HRV recovery? Use the workout_recovery tool. Rank by hrv_change descending."
        },
        Suggestion(label: "Sleep vs HRV") {
            let (start, end) = lastNDaysRange(60)
            return "Between \(start) and \(end), is there a relationship between sleep duration and next-day HRV? Look at days with sleep ≥ 7.5h vs sleep < 6h and compare their HRV the following day."
        },
    ]

    /// Monday–Sunday range of the most recently completed ISO week.
    private static func lastWeekRange() -> (start: String, end: String) {
        var cal = Calendar(identifier: .iso8601)
        cal.firstWeekday = 2  // Monday
        cal.minimumDaysInFirstWeek = 4
        let now = Date()
        let thisWeekStart = cal.date(
            from: cal.dateComponents([.yearForWeekOfYear, .weekOfYear], from: now)
        ) ?? now
        let lastWeekStart = cal.date(byAdding: .day, value: -7, to: thisWeekStart) ?? now
        let lastWeekEnd = cal.date(byAdding: .day, value: 6, to: lastWeekStart) ?? now
        return (isoDate(lastWeekStart), isoDate(lastWeekEnd))
    }

    /// Past N-day window ending yesterday.
    private static func lastNDaysRange(_ n: Int) -> (start: String, end: String) {
        let cal = Calendar(identifier: .iso8601)
        let now = Date()
        let yesterday = cal.date(byAdding: .day, value: -1, to: now) ?? now
        let start = cal.date(byAdding: .day, value: -(n - 1), to: yesterday) ?? yesterday
        return (isoDate(start), isoDate(yesterday))
    }

    private static func isoDate(_ d: Date) -> String {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .iso8601)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: d)
    }

    struct Suggestion: Identifiable {
        let id = UUID()
        let label: String
        let makeQuestion: () -> String
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "sparkles")
                Text("Ask your health graph")
                    .font(.headline)
            }

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(Self.suggestions) { chip in
                        Button(chip.label) {
                            let q = chip.makeQuestion()
                            question = q
                            Task { await submit() }
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.small)
                        .disabled(isLoading)
                    }
                }
            }

            HStack {
                TextField("e.g. Why was my recovery low last week?", text: $question)
                    .textFieldStyle(.roundedBorder)
                    .disabled(isLoading)
                    .onSubmit { Task { await submit() } }
                Button {
                    Task { await submit() }
                } label: {
                    if isLoading {
                        ProgressView()
                    } else {
                        Image(systemName: "arrow.up.circle.fill")
                            .font(.title2)
                    }
                }
                .disabled(isLoading || question.trimmingCharacters(in: .whitespaces).isEmpty)
            }

            if let errorMessage {
                Text(errorMessage)
                    .font(.caption)
                    .foregroundStyle(.red)
            }

            // Hide all inline content while the sheet is showing an answer.
            // Two motivations:
            //   1. Stop the visible duplication where the same answer shows
            //      both behind the dimmed sheet and inside it.
            //   2. Stale entries from earlier app versions (e.g. a "Last week
            //      summary" entry where the chip used to send just the chip
            //      label) don't compete for the user's attention while
            //      they're reading the current answer.
            if expandedEntry == nil {
                if let latest = history.first {
                    Button {
                        expandedEntry = latest
                    } label: {
                        entryCard(latest, isLatest: true)
                    }
                    .buttonStyle(.plain)
                }

                if history.count > 1 {
                    HStack {
                        Text("History")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Spacer()
                        Button("Clear") {
                            history = []
                            QAEntry.saveHistory(history)
                        }
                        .font(.caption)
                        .buttonStyle(.borderless)
                    }
                    .padding(.top, 4)

                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 8) {
                            ForEach(history.dropFirst()) { entry in
                                Button {
                                    expandedEntry = entry
                                } label: {
                                    entryCard(entry, isLatest: false)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                    .frame(maxHeight: 200)
                }
            }
        }
        .padding(.horizontal)
        .padding(.top, 8)
        .sheet(item: $expandedEntry) { entry in
            AnswerSheet(entry: entry)
        }
    }

    @ViewBuilder
    private func entryCard(_ entry: QAEntry, isLatest: Bool) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .top) {
                Text(entry.question)
                    .font(isLatest ? .subheadline.weight(.semibold) : .subheadline.weight(.medium))
                    .multilineTextAlignment(.leading)
                    .lineLimit(isLatest ? 3 : 2)
                Spacer(minLength: 8)
                Image(systemName: "arrow.up.left.and.arrow.down.right")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
            MarkdownText(entry.answer)
                .font(.callout)
                .foregroundStyle(isLatest ? .primary : .secondary)
                .lineLimit(isLatest ? nil : 4)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(10)
        .background(
            (isLatest ? Color.accentColor.opacity(0.08) : Color.gray.opacity(0.08)),
            in: RoundedRectangle(cornerRadius: 8)
        )
        .contentShape(Rectangle())
    }

    private func submit() async {
        let q = question.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty, !isLoading else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            let answer = try await AgentClient.shared.ask(q)
            let entry = QAEntry(id: UUID(), question: q, answer: answer, timestamp: Date())
            history.insert(entry, at: 0)
            if history.count > 10 { history = Array(history.prefix(10)) }
            QAEntry.saveHistory(history)
            question = ""
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

/// Full-screen-ish answer view. Two detents (.medium and .large) so the user
/// can swipe between minimized and maximized, and a drag indicator at the top.
private struct AnswerSheet: View {
    let entry: QAEntry
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text(entry.question)
                        .font(.title3.weight(.semibold))
                        .frame(maxWidth: .infinity, alignment: .leading)
                    MarkdownText(entry.answer)
                        .font(.body)
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .padding()
            }
            .navigationTitle("Answer")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        dismiss()
                    } label: {
                        Label("Dashboard", systemImage: "chevron.left")
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }
}

/// Minimal Markdown renderer for the agent's typical output: paragraphs,
/// `*`/`-` bullets, `N.` numbered lists, and inline `**bold**` / `*italic*` /
/// `` `code` `` via `AttributedString(markdown:)`.
private struct MarkdownText: View {
    private let blocks: [MarkdownBlock]

    init(_ text: String) {
        self.blocks = MarkdownBlock.parse(text)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(blocks) { block in
                switch block.kind {
                case .paragraph:
                    Text(inline(block.content))
                        .fixedSize(horizontal: false, vertical: true)
                case .bullet:
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        Text("•").foregroundStyle(.tertiary)
                        Text(inline(block.content))
                            .fixedSize(horizontal: false, vertical: true)
                    }
                case .numbered(let n):
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        Text("\(n).")
                            .foregroundStyle(.tertiary)
                            .monospacedDigit()
                        Text(inline(block.content))
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
        }
    }

    private func inline(_ s: String) -> AttributedString {
        let opts = AttributedString.MarkdownParsingOptions(
            interpretedSyntax: .inlineOnlyPreservingWhitespace
        )
        return (try? AttributedString(markdown: s, options: opts)) ?? AttributedString(s)
    }
}

private struct MarkdownBlock: Identifiable {
    enum Kind { case paragraph, bullet, numbered(Int) }
    let id: Int
    let kind: Kind
    let content: String

    static func parse(_ text: String) -> [MarkdownBlock] {
        var out: [MarkdownBlock] = []
        var paragraph: [String] = []

        func flush() {
            guard !paragraph.isEmpty else { return }
            let joined = paragraph.joined(separator: " ").trimmingCharacters(in: .whitespaces)
            if !joined.isEmpty {
                out.append(MarkdownBlock(id: out.count, kind: .paragraph, content: joined))
            }
            paragraph = []
        }

        for raw in text.split(separator: "\n", omittingEmptySubsequences: false) {
            let line = String(raw).trimmingCharacters(in: .whitespaces)
            if line.isEmpty { flush(); continue }
            if line.hasPrefix("* ") || line.hasPrefix("- ") {
                flush()
                let content = String(line.dropFirst(2)).trimmingCharacters(in: .whitespaces)
                out.append(MarkdownBlock(id: out.count, kind: .bullet, content: content))
                continue
            }
            // "N. content" — small positive integer + "." + " "
            if let dot = line.firstIndex(of: "."),
               dot > line.startIndex,
               let n = Int(line[line.startIndex..<dot]),
               n > 0,
               line.index(after: dot) < line.endIndex,
               line[line.index(after: dot)] == " " {
                flush()
                let content = String(line[line.index(dot, offsetBy: 2)...])
                    .trimmingCharacters(in: .whitespaces)
                out.append(MarkdownBlock(id: out.count, kind: .numbered(n), content: content))
                continue
            }
            paragraph.append(line)
        }
        flush()
        return out
    }
}

struct QAEntry: Identifiable, Codable {
    let id: UUID
    let question: String
    let answer: String
    let timestamp: Date

    private static let storageKey = "AgentChatHistory_v1"

    static func loadHistory() -> [QAEntry] {
        guard let data = UserDefaults.standard.data(forKey: storageKey),
              let decoded = try? JSONDecoder().decode([QAEntry].self, from: data)
        else { return [] }
        return decoded
    }

    static func saveHistory(_ entries: [QAEntry]) {
        guard let data = try? JSONEncoder().encode(entries) else { return }
        UserDefaults.standard.set(data, forKey: storageKey)
    }
}
