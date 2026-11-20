bool hasSeveralCounters(const fontreal_v3::OutlineSamples &samples,int minimum=2)
{
    constexpr int background=64;
    auto visited=exteriorMask(samples,background);
    const int pitch=samples.pitch, rows=samples.pixels.size()/pitch;
    int count=0;
    for (int start=0; start<pitch*rows; ++start) {
        if (visited[start] || samples.pixels[start]>background)
            continue;
        std::vector<int> queue{start};
        visited[start]=true;
        for (std::size_t i=0; i<queue.size(); ++i) {
            const int at=queue[i], x=at%pitch,y=at/pitch;
            for (const int next:{x?at-1:at,x+1<pitch?at+1:at,y?at-pitch:at,y+1<rows?at+pitch:at}) {
                if (!visited[next] && samples.pixels[next]<=background) {
                    visited[next]=true;
                    queue.push_back(next);
                }
            }
        }
        if (queue.size()>=9 && ++count==minimum)
            return true;
    }
    return false;
}

// Render enclosed bowls from one outline so bridges cannot follow a displaced reference.
std::vector<fontreal_v3::Coverage> balanceBowlInk(const fontreal_v3::OutlineSamples &samples, fontreal_v3::Ink ink, int mode)
{
    using namespace fontreal_v3;
    const int width=samples.frame.width,height=samples.frame.height;
    const bool dark=ink==Ink::Dark;
    std::vector<Coverage> result(width*height);
    struct Section {int y,left,right; double mass;};
    std::vector<Section> sections;
    std::vector<double> widths;
    for (int y=0; y<height; ++y) {
        for (int x=0; x<width;) {
            if (samples.center(x,y)<6) {
                ++x;
                continue;
            }
            const int left=x;
            double mass=0;
            while (x<width && samples.center(x,y)>=6) {
                mass+=samples.center(x,y)/255.;
                ++x;
            }
            sections.push_back({y,left,x,mass});
            if (x-left<=3 && mass>=.38 && mass<=1.04 && y>0 && y+1<height)
                widths.push_back(mass);
        }
    }
    std::sort(widths.begin(),widths.end());
    const double typical=widths.empty() ? .65 : widths[widths.size()/2];
    for (const auto &s:sections) {
        const bool thin=s.right-s.left<=3 && s.mass>=.38 && s.mass<=1.04
                && s.y>0 && s.y+1<height;
        const double normal=s.mass+.47*std::clamp(typical-s.mass,-.19,.19);
        double density=normal*(dark?1.36:.94)+.028;
        if (mode>=13 && dark)
            density=.98+.26*std::clamp(s.mass-typical,-.22,.25);
        for (int x=s.left; x<s.right; ++x) {
            const double area=samples.center(x,s.y)/255.;
            const double crown=std::min(1.,area*(dark?1.26:1.17));
            const double weight=thin ? density*area/s.mass : crown;
            result[s.y*width+x]=encodedInk(std::min(1.,weight),ink);
        }
    }
    return result;
}
