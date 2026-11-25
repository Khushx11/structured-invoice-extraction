import Foundation
import Vision
import ImageIO

guard CommandLine.arguments.count == 2,
      let source = CGImageSourceCreateWithURL(URL(fileURLWithPath: CommandLine.arguments[1]) as CFURL, nil),
      let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
    fputs("Expected a readable image\n", stderr)
    exit(2)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.recognitionLanguages = ["en-US", "en-GB"]
request.usesLanguageCorrection = false
do {
    try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
    var words: [[String: Any]] = []
    for observation in request.results ?? [] {
        guard let candidate = observation.topCandidates(1).first else { continue }
        let text = candidate.string
        for match in try NSRegularExpression(pattern: "\\S+").matches(in: text, range: NSRange(text.startIndex..., in: text)) {
            guard let range = Range(match.range, in: text),
                  let region = try? candidate.boundingBox(for: range) else { continue }
            let box = region.boundingBox
            words.append(["text": String(text[range]), "box": [box.minX, 1 - box.maxY, box.maxX, 1 - box.minY],
                          "confidence": candidate.confidence])
        }
    }
    let data = try JSONSerialization.data(withJSONObject: words)
    FileHandle.standardOutput.write(data)
} catch {
    fputs("OCR failed: \(error)\n", stderr)
    exit(1)
}

