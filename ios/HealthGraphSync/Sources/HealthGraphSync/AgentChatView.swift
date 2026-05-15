import SwiftUI

struct AgentChatView: View {
    @State private var question: String = ""
    @State private var history: [QAEntry] = QAEntry.loadHistory()
    @State private var isLoading = false
    @State private var errorMessage: String?

    private static let suggestions = [
        "Last week summary",
        "Overtraining check",
        "Best workout day",
        "Sleep vs HRV",
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "sparkles")
                Text("Ask your health graph")
                    .font(.headline)
            }

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(Self.suggestions, id: \.self) { chip in
                        Button(chip) {
                            question = chip
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

            if !history.isEmpty {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 12) {
                        ForEach(history) { entry in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(entry.question)
                                    .font(.subheadline.weight(.medium))
                                Text(entry.answer)
                                    .font(.callout)
                                    .foregroundStyle(.secondary)
                                    .textSelection(.enabled)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(8)
                            .background(Color.gray.opacity(0.08), in: RoundedRectangle(cornerRadius: 8))
                        }
                    }
                }
                .frame(maxHeight: 240)
            }
        }
        .padding(.horizontal)
        .padding(.top, 8)
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
