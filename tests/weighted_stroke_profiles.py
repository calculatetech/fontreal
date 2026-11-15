"""Experimental core darkening; no neighboring coverage is removed."""
from thin_stroke_profiles import normalize


def darken(raw, preferred, width):
    _, selector = normalize(raw, preferred, width)
    positive = sorted(v for v in preferred if v)
    cutoff = positive[-((len(positive)+3)//4)] if positive else 0
    references = [v for v in positive if v >= cutoff]
    numerator = sum(v*v for v in references); denominator = sum(references)
    target = (2*numerator+denominator)//(2*denominator) if denominator else 0
    cores = {p['core'] for lane in selector['lanes'] for p in lane['pairs']}
    fringes = {p['fringe'] for lane in selector['lanes'] for p in lane['pairs']}
    stems = bytearray(preferred)
    for i in cores: stems[i] = max(stems[i], target)
    extended = bytearray(stems); peaks = []
    if cores:
        height = len(raw)//width
        def neighbors(i):
            x,y = i % width, i // width
            return [yy*width+xx for yy in range(max(0,y-1),min(height,y+2))
                    for xx in range(max(0,x-1),min(width,x+2)) if (xx,yy) != (x,y)]
        pending = {i for i,v in enumerate(preferred) if v >= 170}
        while pending:
            first = min(pending); pending.remove(first); component = {first}; todo = [first]
            while todo:
                for j in neighbors(todo.pop()):
                    if j in pending:
                        pending.remove(j); component.add(j); todo.append(j)
            if not component & cores or sum(preferred[i] >= cutoff for i in component) < 2: continue
            for i in sorted(component - cores - fringes):
                v = preferred[i]
                if not 170 <= v < min(target,230): continue
                x,y = i % width, i // width
                left = preferred[i-1] if x else 0
                right = preferred[i+1] if x+1 < width else 0
                up = preferred[i-width] if y else 0
                down = preferred[i+width] if y+1 < height else 0
                if v > max(left,right) or v > max(up,down):
                    extended[i] = target; peaks.append(i)
    outputs = dict(stems=bytes(stems),connected=bytes(extended))
    for values in outputs.values():
        assert all(b >= p and bool(a) == bool(b) and (p < 230 or p == b)
                   for a,p,b in zip(raw,preferred,values,strict=True))
    return outputs, dict(target=target,reference_cutoff=cutoff,reference_count=len(references),
                        numerator=numerator,denominator=denominator,cores=sorted(cores),
                        peaks=sorted(peaks),selector=selector)
